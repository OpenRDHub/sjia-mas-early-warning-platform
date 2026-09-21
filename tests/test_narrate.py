import pytest

from rareguard.analysis.rules import RuleHit
from rareguard.analysis.mas import Assessment
from rareguard.llm.provider import BaseLLMProvider, LLMResponse
from rareguard.narrate import narrate, template_text, build_prompt


def a_red():
    return Assessment(
        level="red", score=87.5,
        hits=(RuleHit("A1", "铁蛋白升高", "red",
                      {"value": 1200, "date": "2026-02-18", "code": "ferritin"}),))


def a_green():
    return Assessment(level="green", score=0.0, hits=())


class Echo(BaseLLMProvider):
    name = "echo"
    reply = "家长您好，孩子多项指标出现变化，建议尽快复诊。"

    def chat(self, messages, tools=None):
        return LLMResponse(text=self.reply, model=self.name)


class Boom(BaseLLMProvider):
    name = "boom"

    def chat(self, messages, tools=None):
        raise RuntimeError("network down")


class Violating(Echo):
    reply = "你孩子确诊MAS，按泼尼松龙每天30mg剂量用药，停药会危险。"


def test_narrate_llm_ok():
    text, meta = narrate(a_red(), Echo(), trace_id="t1")
    assert meta["source"] == "llm" and "医生诊断" in text


def test_narrate_guard_blocks_diagnosis():
    text, meta = narrate(a_red(), Violating(), trace_id="t2")
    assert "确诊" not in text and "剂量" not in text and "30mg" not in text


def test_narrate_provider_failure_falls_back_template():
    text, meta = narrate(a_red(), Boom(), trace_id="t3")
    assert meta["source"] == "template"
    assert "24小时" in text


def test_template_levels():
    assert "24小时" in template_text(a_red())
    assert "继续观察" in template_text(a_green())


def test_build_prompt_contains_evidence():
    p = build_prompt(a_red())
    assert "ferritin" in p and "1200" in p
