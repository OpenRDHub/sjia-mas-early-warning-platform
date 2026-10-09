"""真实 LLM 全流程评测（real_api marker）：多轮采集→EHR 读取→成文→管道闭环。

Mock EHR 脱敏数据 + 真实模型（当前 MiMo v2.5 Pro）；限流由 Provider 层
429 退避兜底，整轮约数分钟。P0a 出口门禁仍以 Mock 门禁为准，本评测
用于积累真实模型行为数据（§7：模型变更后全量回归）。
"""

import pytest

from evals.runner import load_cases
from rareguard.ehr.mock_provider import MockEHRProvider
from rareguard.llm.openai_compat_provider import (
    OpenAICompatProvider,
    is_configured,
)
from rareguard.orchestrator.graph import (
    handle_patient_input,
    sign_consent,
    start_session,
)

pytestmark = [
    pytest.mark.real_api,
    pytest.mark.skipif(
        not is_configured(),
        reason="未配置 MEDASSIST_LLM_*（环境变量或 .env），跳过真实评测",
    ),
]

_NORMAL_CASES = load_cases("normal")


@pytest.mark.parametrize(
    "case", _NORMAL_CASES, ids=[c["id"] for c in _NORMAL_CASES]
)
def test_real_full_flow(case):
    llm = OpenAICompatProvider(timeout=180.0)
    ehr = MockEHRProvider()
    s = start_session(f"real-{case['id']}", case.get("patient_id", "P001"))
    sign_consent(s)
    for text in case["inputs"]:
        s = handle_patient_input(s, text, llm, ehr=ehr)
    # 主链路必须走通：成文并进入医生复核，管道全绿
    assert s.state.value == "review", f"最终状态 {s.state.value}"
    assert s.pipeline_ok and s.draft

    # 真实模型有两种合规结局：干净草稿 / 被 L4 拦截替换（如模型编造剂量）
    intercepted = "拦截" in s.draft  # L4 兜底文案特征
    if not intercepted:
        # 留白协议：缺失项以 N5_SYSTEM 规定的 — 标记，或文字标注待补充
        assert "—" in s.draft or "补充" in s.draft
        # 安全关键：EHR 过敏史必须进入草稿（医生复核必看）
        if case.get("patient_id", "P001") == "P001":
            assert "青霉素" in s.draft, f"过敏史未进入草稿：{s.draft[:300]}"
        # 当前用药应进入草稿（EHR 上下文直接引用）
        if case.get("patient_id") == "P002":
            assert "氯雷他定" in s.draft, f"当前用药未进入草稿：{s.draft[:300]}"
    # 被拦截亦是合规结局：L4 兜底文案 + 医生复核（护栏对真实模型的价值）
