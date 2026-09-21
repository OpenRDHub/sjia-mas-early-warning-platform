"""编排节点与会话驱动（§4.2）：N1 采集 / N2 检索(占位) / N3 数据 / N5 成文。

- N4 风险旁路在 handle_patient_input 内联实现（独立通道，绝不经 LLM，红色直推护士站并留痕）
- N5 成文后强制经 run_verification_pipeline（§5：所有 LLM 输出返回终端前必须过管道）
- LangGraph 图执行在 P0b 接入；P0a 用纯 Python 驱动，状态语义与 §4.1 图一致
"""

import json
from pathlib import Path

from rareguard.ehr.provider import BaseEHRProvider, PatientNotFound
from rareguard.llm.provider import BaseLLMProvider, extract_json
from rareguard.orchestrator.state import (
    InvalidTransition,
    Session,
    SessionStatus,
    transition,
)
from rareguard.risk.rules import assess
from rareguard.verification.audit import log_event
from rareguard.verification.input_guard import check_input
from rareguard.verification.pipeline import run_verification_pipeline

# 采集轮次保护：超限强制成文，防止患者被困在无限追问（§4.1 状态机防御）
MAX_INTAKE_TURNS = 6

N1_SYSTEM = (
    "N1 采集节点：你是门诊预问诊助手，严禁输出任何疾病判断或用药建议。"
    "根据对话抽取结构化槽位并以 JSON 返回："
    '{"slots": {...}, "next_question": "...", "collecting_done": bool}。'
    "槽位：chief_complaint/duration/severity/associated。"
    "信息不足时用 next_question 继续询问，绝不编造。"
    "完成判据：主诉（chief_complaint）与病程（duration）均已获得即置"
    " collecting_done=true 立即完成采集，其余槽位留给医生，不得过度追问。"
)

N5_SYSTEM = (
    "N5 成文节点：根据给定槽位与 EHR 上下文生成 SOAP 病历草稿。"
    "缺失槽位标记为 —（待医生补充），严禁填写 A（评估/诊断）与 P（处方）内容——"
    "100% 留给执业医师。"
    "引用 EHR 当前用药时只列药名，严禁添加剂量、频次或任何用药建议——"
    "上下文未提供的信息一律不得编造。"
)


def start_session(session_id: str, patient_id: str) -> Session:
    """创建会话：INIT → CONSENT（等待签署知情同意）。"""
    s = Session(session_id=session_id, patient_id=patient_id)
    transition(s, SessionStatus.CONSENT)
    s.last_reply = "欢迎使用预问诊服务。本服务仅辅助信息采集，医生为责任主体。请阅读并同意知情同意书。"
    return s


def sign_consent(session: Session) -> Session:
    """患者签署知情同意：CONSENT → COLLECTING。"""
    transition(session, SessionStatus.COLLECTING)
    session.last_reply = "感谢您的同意。请问您今天最主要的不适是什么？"
    return session


def handle_patient_input(
    session: Session,
    text: str,
    llm: BaseLLMProvider,
    ehr: BaseEHRProvider | None = None,
    audit_path: Path | None = None,
) -> Session:
    """患者一轮输入：L1 净化 → N4 风险旁路 → N1 采集（COLLECTING/PROBING）。"""
    if session.state not in (SessionStatus.COLLECTING, SessionStatus.PROBING):
        raise InvalidTransition(
            f"状态 {session.state.value} 不接受患者输入"
        )

    # L1 输入净化：被拒输入不得进入对话历史
    v = check_input(text)
    if not v.ok:
        session.last_reply = "本轮输入未通过安全校验，请重新描述您的症状。"
        return session

    session.messages.append({"role": "user", "content": text})

    # N4 风险旁路（独立通道，不经 LLM）：红色直推护士站
    ra = assess(text)
    if ra.level == "red":
        session.risk_level, session.risk_rules = "red", ra.matched
        log_event(
            {
                "event": "risk_alert",
                "trace_id": session.trace_id,
                "session_id": session.session_id,
                "patient_id": session.patient_id,
                "rules": list(ra.matched),
                "input": text,
            },
            path=audit_path,
        )
        transition(session, SessionStatus.ALERT)
        session.last_reply = (
            "您的症状可能较为紧急，已通知护士站优先处理。"
            "请在原地休息，若不适加重请立即呼叫工作人员。"
        )
        return session
    if ra.level == "yellow" and session.risk_level != "red":
        session.risk_level, session.risk_rules = "yellow", ra.matched

    # N1 采集：LLM 返回合并槽位 + 下一问
    payload = json.dumps(
        {"text": text, "known_slots": session.slots}, ensure_ascii=False
    )
    resp = llm.chat(
        [{"role": "system", "content": N1_SYSTEM},
         *session.messages[:-1],
         {"role": "user", "content": payload}]
    )
    data = extract_json(resp.text)  # 真实模型可能以 markdown 代码块包裹
    gained = data["slots"] != session.slots
    session.slots = data["slots"]
    question = data["next_question"]
    session.messages.append({"role": "assistant", "content": question})
    session.last_reply = question

    user_turns = sum(1 for m in session.messages if m["role"] == "user")
    if data["collecting_done"] or user_turns >= MAX_INTAKE_TURNS:
        _complete_intake(session, llm, ehr, audit_path)
        session.last_reply = "预问诊已完成，问诊摘要与病历草稿已推送至医生工作站，请等待叫号。"
        return session

    # 有信息增量回到/保持 COLLECTING；无增量转 PROBING（澄清式追问）
    target = (
        SessionStatus.COLLECTING if gained else SessionStatus.PROBING
    )
    if session.state != target:
        transition(session, target)
    return session


def _complete_intake(
    session: Session,
    llm: BaseLLMProvider,
    ehr: BaseEHRProvider | None,
    audit_path: Path | None,
) -> None:
    """采集完成：N3 数据 → N2 检索(占位) → N5 成文 → 管道校验 → REVIEW。"""
    transition(session, SessionStatus.RETRIEVING)
    ehr_ctx = _load_ehr_context(ehr, session.patient_id)  # N3 只读
    references: list = []  # N2：RAG 知识库 P1 建设后接入

    transition(session, SessionStatus.DRAFTING)
    prompt = json.dumps(
        {"slots": session.slots, "ehr": ehr_ctx, "references": references},
        ensure_ascii=False,
    )
    resp = llm.chat(
        [{"role": "system", "content": N5_SYSTEM},
         {"role": "user", "content": prompt}]
    )

    # §5：所有 LLM 输出返回终端前必须经管道
    last_user = next(
        (m["content"] for m in reversed(session.messages) if m["role"] == "user"),
        "",
    )
    # L3 事实接地上下文：患者口述槽位 + EHR 原文（数值断言唯一合法出处）
    pr = run_verification_pipeline(
        user_input=last_user,
        llm_output=resp.text,
        trace_id=session.trace_id,
        audit_path=audit_path,
        fact_context=prompt,
    )
    session.pipeline_ok = pr.ok
    session.draft = pr.text if pr.ok else ""  # 阻断内容不得作为草稿展示
    transition(session, SessionStatus.REVIEW)


def _load_ehr_context(ehr: BaseEHRProvider | None, patient_id: str) -> str:
    """N3：经只读适配层拉取患者历史，拼成草稿 O 段上下文。

    用药史只列药名不带剂量/频次——历史处方细节进入输出会触发 L4
    剂量拦截，且对预问诊无增量价值，医生可在工作站查看详情。
    """
    if ehr is None:
        return ""
    try:
        meds = "、".join(
            m["name"] for m in ehr.get_medications(patient_id)
        )
        allergies = "、".join(
            f"{a['substance']}（{a['reaction']}）"
            for a in ehr.get_allergies(patient_id)
        )
        encounters = "；".join(
            f"{e['date']} {e['dept']} {e['summary']}"
            for e in ehr.get_encounters(patient_id)[:3]
        )
    except PatientNotFound:
        return ""
    parts = []
    if encounters:
        parts.append(f"既往就诊：{encounters}")
    if meds:
        parts.append(f"当前用药：{meds}")
    if allergies:
        parts.append(f"过敏史：{allergies}")
    return "；".join(parts)


def confirm_draft(session: Session, notes: str = "") -> Session:
    """医生复核确认：REVIEW → DONE，修改意见留痕（§6.4 diff 留存基础）。"""
    transition(session, SessionStatus.DONE)
    session.review_notes = notes
    session.last_reply = "医生已确认病历。"
    return session
