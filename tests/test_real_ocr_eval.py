import json

from evals.real_ocr_eval import evaluate_samples
from rareguard.llm.provider import BaseLLMProvider, LLMResponse


class _MatchOCR(BaseLLMProvider):
    name = "m"

    def chat(self, messages, tools=None):
        return LLMResponse(text=json.dumps({"items": [
            {"name": "Serum Ferritin", "value": 1200, "unit": "ng/mL",
             "ref_low": 15, "ref_high": 150}]}), model=self.name)


def _sample(tmp):
    (tmp / "lab1.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    label = [{"name": "血清铁蛋白", "code": "ferritin", "value": 1200,
              "unit": "ng/mL", "ref_low": 15, "ref_high": 150}]
    (tmp / "lab1.json").write_text(
        json.dumps(label, ensure_ascii=False), encoding="utf-8")


def test_evaluate_samples_full_accuracy(tmp_path):
    _sample(tmp_path)
    r = evaluate_samples(tmp_path, _MatchOCR())
    assert r["files"] == 1 and r["mean_accuracy"] == 1.0


def test_evaluate_samples_empty_returns_none(tmp_path):
    assert evaluate_samples(tmp_path, _MatchOCR()) is None


def test_evaluate_samples_scores_mismatch_below_one(tmp_path):
    (tmp_path / "lab1.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    label = [{"name": "血清铁蛋白", "code": "ferritin", "value": 999,
              "unit": "ng/mL", "ref_low": 15, "ref_high": 150}]
    (tmp_path / "lab1.json").write_text(
        json.dumps(label, ensure_ascii=False), encoding="utf-8")
    r = evaluate_samples(tmp_path, _MatchOCR())
    assert 0.0 <= r["mean_accuracy"] < 1.0
