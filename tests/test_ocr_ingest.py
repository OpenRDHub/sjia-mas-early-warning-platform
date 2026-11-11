import json
import pytest

from rareguard.data.store import Store
from rareguard.ingest.ocr import parse_lab_report, parse_dual, commit_confirmed
from rareguard.llm.provider import BaseLLMProvider, LLMResponse

_ITEMS = [
    {"name": "血清铁蛋白", "value": 620, "unit": "ng/mL",
     "ref_low": 7, "ref_high": 140},
    {"name": "C反应蛋白", "value": 45, "unit": "mg/L",
     "ref_low": 0, "ref_high": 8},
    {"name": "血小板", "value": 90, "unit": "10^9/L",
     "ref_low": 150, "ref_high": 450},
]


class ScriptedOCR(BaseLLMProvider):
    """按脚本队列返回 OCR JSON；队列耗尽返回最后一项。"""
    name = "scripted"

    def __init__(self, payloads):
        self.payloads = list(payloads)

    def chat(self, messages, tools=None):
        p = self.payloads.pop(0) if len(self.payloads) > 1 else self.payloads[0]
        return LLMResponse(text="```json\n" + json.dumps(
            {"items": p}, ensure_ascii=False) + "\n```", model=self.name)


def test_parse_normalizes_aliases():
    items = parse_lab_report("Zm9v", ScriptedOCR([_ITEMS]))
    codes = [i["code"] for i in items]
    assert codes == ["ferritin", "crp", "plt"]
    assert all(not i["needs_review"] for i in items)


def test_unknown_indicator_flagged():
    p = _ITEMS + [{"name": "血糖", "value": 5.1, "unit": "mmol/L",
                   "ref_low": 3, "ref_high": 6}]
    items = parse_lab_report("Zm9v", ScriptedOCR([p]))
    glu = [i for i in items if i["name"] == "血糖"][0]
    assert glu["code"] is None and glu["needs_review"]


def test_dual_consistent_all_confirmed():
    items = parse_dual("Zm9v", ScriptedOCR([_ITEMS]))
    assert all(not i["needs_review"] for i in items)


def test_dual_disagreement_marks_needs_review():
    second = [dict(_ITEMS[0]), dict(_ITEMS[1]), dict(_ITEMS[2])]
    second[1]["value"] = 39
    items = parse_dual("Zm9v", ScriptedOCR([_ITEMS, second]))
    crp = [i for i in items if i["code"] == "crp"][0]
    assert crp["needs_review"]
    assert not [i for i in items if i["code"] == "ferritin"][0]["needs_review"]


def test_commit_confirmed_only(tmp_path):
    second = [dict(_ITEMS[0]), dict(_ITEMS[1]), dict(_ITEMS[2])]
    second[1]["value"] = 39
    items = parse_dual("Zm9v", ScriptedOCR([_ITEMS, second]))
    s = Store(str(tmp_path / "t.db"))
    s.add_patient("P01", "小明", "2015-06-01")
    n = commit_confirmed(s, "P01", "2026-01-08", items)
    assert n == 2
    codes = [r[0] for r in s.rows(
        "SELECT code FROM lab WHERE pid='P01' ORDER BY code", ())]
    assert codes == ["ferritin", "plt"]
    s.close()
