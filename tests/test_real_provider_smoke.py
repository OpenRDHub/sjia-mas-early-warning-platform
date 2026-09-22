"""真实 LLM Provider 冒烟 + 协议回归（未配置密钥自动跳过）。

验证 §3.2 核心假设：接入真实模型后，N1/N5 协议与护栏依然成立——
换模型不改护栏。使用 Mock 脱敏数据，不涉真实患者信息。
"""

import json

import pytest
import requests

from rareguard.llm.openai_compat_provider import (
    OpenAICompatProvider,
    extract_json,
    is_configured,
)

pytestmark = [
    pytest.mark.real_api,
    pytest.mark.skipif(
        not is_configured(),
        reason="未配置 MEDASSIST_LLM_*（环境变量或 .env），跳过真实 API 冒烟",
    ),
]


@pytest.fixture(scope="module")
def provider():
    # 书生 intern-latest 生成长文本较慢，超时放宽到 180s
    return OpenAICompatProvider(timeout=180.0)


def test_chat_connectivity(provider):
    resp = provider.chat([
        {"role": "system", "content": "你是连通性测试助手，只回复：pong"},
        {"role": "user", "content": "ping"},
    ])
    assert resp.text.strip()
    assert resp.model


def test_n1_protocol_with_real_model(provider):
    """N1 采集协议：真实模型须按 JSON 协议返回槽位与下一问。"""
    from rareguard.orchestrator.graph import N1_SYSTEM

    payload = json.dumps(
        {"text": "我胸口疼，疼了三天了", "known_slots": {}}, ensure_ascii=False
    )
    resp = provider.chat([
        {"role": "system", "content": N1_SYSTEM},
        {"role": "user", "content": payload},
    ])
    data = extract_json(resp.text)
    assert {"slots", "next_question", "collecting_done"} <= set(data)
    # 真实模型应至少抽到主诉或时长之一（宽松断言，输出有随机性）
    assert data["slots"].get("chief_complaint") or data["slots"].get("duration")


def test_n5_draft_with_real_model_passes_pipeline(provider, tmp_path):
    """N5 成文协议：真实模型草稿过验证管道——干净通过或被正确拦截均算协议闭环。"""
    from rareguard.orchestrator.graph import N5_SYSTEM
    from rareguard.verification.pipeline import run_verification_pipeline

    payload = json.dumps(
        {
            "slots": {
                "chief_complaint": "胸痛", "duration": "三天",
                "severity": "中等", "associated": "出汗",
            },
            "ehr": "过敏史：青霉素（皮疹）",
            "references": [],
        },
        ensure_ascii=False,
    )
    messages = [
        {"role": "system", "content": N5_SYSTEM},
        {"role": "user", "content": payload},
    ]
    resp = None
    for attempt in range(2):  # 云端生成方差大，容忍一次超时重试
        try:
            resp = provider.chat(messages)
            break
        except requests.exceptions.ReadTimeout:
            if attempt == 1:
                raise
    assert resp is not None
    pr = run_verification_pipeline(
        user_input="我胸痛三天",
        llm_output=resp.text,
        trace_id="smoke-n5",
        audit_path=tmp_path / "a.jsonl",
    )
    # 管道必须给出自洽结果
    if pr.ok:
        # 干净通过：草稿须遵守 N5 协议精神——缺失槽位标注待补充、不编造。
        # 真实模型表达多样（待医生补充/待补充/需由执业医师补充均含"补充"；
        # 也有模型直接用协议占位符"—"），两种协议记号任一即算合规。
        assert "补充" in pr.text or "—" in pr.text
    else:
        # 被拦截：必须有明确原因（这正是护栏对真实模型的价值）
        assert pr.layers and any(
            v.get("reason") for v in pr.layers.values() if isinstance(v, dict)
        )
