import json

import pytest

from rareguard.llm.mock_provider import MockLLMProvider
from rareguard.llm.provider import BaseLLMProvider, LLMResponse
from rareguard.orchestrator.graph import N1_SYSTEM, N5_SYSTEM


def test_base_provider_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseLLMProvider()


def _n1_call(text: str, known: dict | None = None):
    llm = MockLLMProvider()
    resp = llm.chat([
        {"role": "system", "content": N1_SYSTEM},
        {"role": "user", "content": json.dumps(
            {"text": text, "known_slots": known or {}}, ensure_ascii=False
        )},
    ])
    return resp, json.loads(resp.text)


def test_mock_n1_extracts_symptom_and_asks_duration():
    resp, data = _n1_call("我胸口疼")
    assert isinstance(resp, LLMResponse)
    assert data["slots"]["chief_complaint"] == "胸口疼"
    assert not data["collecting_done"]
    assert "多久" in data["next_question"] or "持续" in data["next_question"]


def test_mock_n1_completes_when_complaint_and_duration_present():
    _, data = _n1_call("疼了三天", known={"chief_complaint": "胸口疼"})
    assert data["collecting_done"]
    assert data["slots"]["duration"] == "三天"
    # 已知槽位必须保留（合并语义，供续答/中断恢复）
    assert data["slots"]["chief_complaint"] == "胸口疼"


def test_mock_n1_probing_when_no_new_info():
    _, data = _n1_call("嗯嗯", known={"chief_complaint": "胸口疼"})
    assert not data["collecting_done"]
    assert data["slots"] == {"chief_complaint": "胸口疼"}


def test_mock_n5_draft_marks_missing_slots_and_keeps_assessment_empty():
    llm = MockLLMProvider()
    resp = llm.chat([
        {"role": "system", "content": N5_SYSTEM},
        {"role": "user", "content": json.dumps(
            {"slots": {"chief_complaint": "胸痛", "duration": "三天"},
             "ehr": "过敏史：青霉素（皮疹）"},
            ensure_ascii=False,
        )},
    ])
    text = resp.text
    assert "S（主观）" in text and "O（客观）" in text
    # R1 红线的模板级落地：A/P 100% 留给医生
    assert "A（评估）：【待医生补充】" in text
    assert "P（处理）：【待医生补充】" in text
    # 缺失槽位（程度）标记待补充，而非编造
    assert "待医生补充" in text.split("O（客观）")[0]
    # EHR 过敏史进入客观段
    assert "青霉素" in text
