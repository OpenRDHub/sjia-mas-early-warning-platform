import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from prime_offline_cache import demo_lab_png_b64, prime_ocr_cache  # noqa: E402

from rareguard.ingest.ocr import parse_lab_report  # noqa: E402
from rareguard.llm.offline_provider import CachedOCR  # noqa: E402
from rareguard.llm.provider import BaseLLMProvider, LLMResponse  # noqa: E402


class FixedOCR(BaseLLMProvider):
    name = "fixed"

    def chat(self, messages, tools=None):
        items = {"items": [
            {"name": "Serum Ferritin", "value": 1200, "unit": "ng/mL",
             "ref_low": 15, "ref_high": 150},
            {"name": "Platelet Count", "value": 80, "unit": "10^9/L",
             "ref_low": 125, "ref_high": 350},
        ]}
        return LLMResponse(text=json.dumps(items), model=self.name)


def test_prime_then_offline_hit(tmp_path):
    b64 = demo_lab_png_b64()
    cache = tmp_path / "ocr_cache"
    prime_ocr_cache(b64, FixedOCR(), cache)
    assert any(cache.glob("*.json"))
    items = parse_lab_report(b64, CachedOCR(cache))
    ferr = next(i for i in items if i["code"] == "ferritin")
    assert ferr["value"] == 1200 and not ferr["needs_review"]


def test_demo_png_saves_file(tmp_path):
    out = tmp_path / "lab.png"
    b64 = demo_lab_png_b64(out)
    assert out.exists() and out.stat().st_size > 0 and b64
