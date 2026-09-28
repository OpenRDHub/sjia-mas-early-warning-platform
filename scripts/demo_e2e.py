"""端到端演示脚本（W4 彩排与路演现场用）：建档→打卡→OCR 上传→趋势→红色预警。

离线演示：python scripts/demo_e2e.py（mock provider，零网络依赖）。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from rareguard.api.home import create_home_app  # noqa: E402
from rareguard.data.store import Store  # noqa: E402
from rareguard.llm.provider import BaseLLMProvider, LLMResponse  # noqa: E402

_OCR_ITEMS = {"items": [
    {"name": "血清铁蛋白", "value": 1200, "unit": "ng/mL",
     "ref_low": 15, "ref_high": 150},
    {"name": "血小板计数", "value": 80, "unit": "10^9/L",
     "ref_low": 125, "ref_high": 350},
    {"name": "纤维蛋白原", "value": 1.2, "unit": "g/L",
     "ref_low": 2, "ref_high": 4},
]}


class DemoOCR(BaseLLMProvider):
    name = "demo-ocr"

    def chat(self, messages, tools=None):
        return LLMResponse(text=json.dumps(_OCR_ITEMS, ensure_ascii=False),
                           model=self.name)


class DemoNarrate(BaseLLMProvider):
    name = "demo-narrate"

    def chat(self, messages, tools=None):
        return LLMResponse(text="家长您好，孩子多项指标明显异常，建议尽快就诊。",
                           model=self.name)


def demo_flow(store_path: str) -> dict:
    """完整走一遍家庭端链路，返回各步结果（供演示打印与测试断言）。"""
    store = Store(store_path)
    app = create_home_app(store, DemoOCR(), DemoNarrate())
    out = {}
    with TestClient(app) as c:
        r = c.post("/api/home/patients", json={
            "pid": "PDEMO", "name": "演示患儿", "dob": "2016-05-01"})
        out["create_patient"] = r.status_code
        out["checkins"] = []
        for day, temp in [("2026-03-03", 39.2), ("2026-03-04", 39.4),
                          ("2026-03-05", 39.6)]:
            rr = c.post("/api/home/checkin", json={
                "pid": "PDEMO", "date": day, "temp": temp,
                "symptoms": {"乏力": 6}})
            out["checkins"].append(rr.status_code)
        up = c.post("/api/home/labs/upload", json={
            "pid": "PDEMO", "date": "2026-03-05", "image_b64": "DEMO"})
        out["upload"] = up.json()
        tr = c.get("/api/home/trend/PDEMO?as_of=2026-03-05&days=7")
        out["trend"] = tr.json()["points"]
        rk = c.get("/api/home/risk/PDEMO?as_of=2026-03-05")
        out["risk"] = rk.json()
        mn = c.post("/api/home/labs/manual", json={
            "pid": "PDEMO", "date": "2026-03-05",
            "items": [{"name": "甘油三酯", "value": 3.6,
                       "unit": "mmol/L"}]})
        out["manual"] = mn.json()
    store.close()
    return out


if __name__ == "__main__":
    import tempfile

    db = str(Path(tempfile.mkdtemp()) / "demo.db")
    result = demo_flow(db)
    print(json.dumps(result, ensure_ascii=False, indent=2))
