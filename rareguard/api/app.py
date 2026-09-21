"""FastAPI 服务层（§4.3 接口契约）：患者端 / 医生端 / 护士站端点。

P0a：内存存储 + Mock Provider，本机/内网开发用；
P0b：认证/限流 + 持久化 + 真实 Provider——仅改依赖注入点（换模型不改护栏）。
患者端与医生端路径分离，RBAC 在 P0b 接入。
"""

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from rareguard.api.store import create_store
from rareguard.ehr.mock_provider import MockEHRProvider
from rareguard.llm.mock_provider import MockLLMProvider
from rareguard.orchestrator.graph import (
    confirm_draft,
    handle_patient_input,
    sign_consent,
    start_session,
)
from rareguard.orchestrator.state import InvalidTransition, SessionStatus

app = FastAPI(title="辅助问诊服务", version="0.1.0")
store = create_store()  # MEDASSIST_STORE=sqlite 切持久化（中断续答）

# 依赖注入点：接真实模型只改这里
_llm = MockLLMProvider()
_ehr = MockEHRProvider()

_INPUT_STATES = (SessionStatus.COLLECTING, SessionStatus.PROBING)


class CreateSessionReq(BaseModel):
    patient_id: str


class MessageReq(BaseModel):
    text: str


class ConfirmReq(BaseModel):
    notes: str = ""


@app.post("/sessions")
def create_session(req: CreateSessionReq):
    """患者扫码创建会话：INIT → CONSENT（等待签署知情同意）。"""
    sid = f"S-{uuid4().hex[:12]}"
    s = start_session(sid, req.patient_id)
    store.save(s)
    return {
        "session_id": sid,
        "trace_id": s.trace_id,
        "state": s.state.value,
        "reply": s.last_reply,
    }


@app.post("/sessions/{sid}/consent")
def consent(sid: str):
    """患者签署知情同意：CONSENT → COLLECTING，返回首问。"""
    s = store.get(sid)
    if not s:
        raise HTTPException(404, "会话不存在")
    try:
        sign_consent(s)
    except InvalidTransition:
        raise HTTPException(409, f"状态 {s.state.value} 不可签署同意")
    return {"state": s.state.value, "reply": s.last_reply}


@app.post("/sessions/{sid}/messages")
def send_message(sid: str, req: MessageReq):
    """患者一轮输入：L1 净化 → N4 风险旁路 → N1 采集；红色直推护士站。"""
    s = store.get(sid)
    if not s:
        raise HTTPException(404, "会话不存在")
    if s.state not in _INPUT_STATES:
        raise HTTPException(409, f"状态 {s.state.value} 不接受患者输入")
    s = handle_patient_input(s, req.text, _llm, ehr=_ehr)
    store.save(s)
    if s.state == SessionStatus.ALERT:
        store.add_alert(
            {
                "session_id": s.session_id,
                "patient_id": s.patient_id,
                "trace_id": s.trace_id,
                "risk_rules": list(s.risk_rules),
            }
        )
        return {
            "state": s.state.value,
            "reply": s.last_reply,
            "risk_rules": list(s.risk_rules),
        }
    resp = {"state": s.state.value, "reply": s.last_reply}
    if s.state == SessionStatus.REVIEW:
        resp["draft_ready"] = True
    return resp


@app.get("/sessions/{sid}/draft")
def get_draft(sid: str):
    """医生端：REVIEW 态返回草稿、槽位与风险（阻断时草稿为空）。"""
    s = store.get(sid)
    if not s:
        raise HTTPException(404, "会话不存在")
    if s.state != SessionStatus.REVIEW:
        raise HTTPException(409, f"状态 {s.state.value} 无草稿")
    return {
        "trace_id": s.trace_id,
        "state": s.state.value,
        "pipeline_ok": s.pipeline_ok,
        "risk_level": s.risk_level,
        "risk_rules": list(s.risk_rules),
        "slots": s.slots,
        "draft": s.draft,
    }


@app.post("/sessions/{sid}/confirm")
def confirm(sid: str, req: ConfirmReq | None = None):
    """医生端：复核确认 REVIEW → DONE，修改意见留痕（body 可省略）。"""
    s = store.get(sid)
    if not s:
        raise HTTPException(404, "会话不存在")
    try:
        confirm_draft(s, notes=req.notes if req else "")
    except InvalidTransition:
        raise HTTPException(409, f"状态 {s.state.value} 不可确认")
    return {"state": s.state.value, "reply": s.last_reply}


@app.get("/alerts")
def alerts():
    """护士站：红色告警队列（最新在前）。"""
    queue = store.alerts()
    return {"count": len(queue), "alerts": list(reversed(queue))}


# ---------- 前端页面（最小原型：单文件静态页） ----------

_STATIC = Path(__file__).parent / "static"


@app.get("/", include_in_schema=False)
def patient_page():
    return FileResponse(_STATIC / "index.html")


@app.get("/doctor", include_in_schema=False)
def doctor_page():
    return FileResponse(_STATIC / "doctor.html")


@app.get("/nurse", include_in_schema=False)
def nurse_page():
    return FileResponse(_STATIC / "nurse.html")
