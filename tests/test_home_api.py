import json

import pytest
from fastapi.testclient import TestClient

from rareguard.api.home import create_home_app
from rareguard.data.store import Store
from rareguard.llm.provider import BaseLLMProvider, LLMResponse

_OCR_JSON = json.dumps({"items": [
    {"name": "血清铁蛋白", "value": 1200, "unit": "ng/mL",
     "ref_low": 15, "ref_high": 150},
    {"name": "血小板计数", "value": 80, "unit": "10^9/L",
     "ref_low": 125, "ref_high": 350},
    {"name": "血糖", "value": 5.1, "unit": "mmol/L",
     "ref_low": 3.9, "ref_high": 6.1},
]}, ensure_ascii=False)


class MockOCR(BaseLLMProvider):
    name = "mock-ocr"

    def chat(self, messages, tools=None):
        return LLMResponse(text=_OCR_JSON, model=self.name)


class MockNarrate(BaseLLMProvider):
    name = "mock-narrate"

    def chat(self, messages, tools=None):
        return LLMResponse(text="家长您好，孩子多项指标明显异常，建议尽快就诊。",
                           model=self.name)


@pytest.fixture()
def client(tmp_path):
    store = Store(str(tmp_path / "home.db"))
    app = create_home_app(store, MockOCR(), MockNarrate())
    with TestClient(app) as c:
        c.store = store
        yield c
    store.close()


def test_create_patient(client):
    r = client.post("/api/home/patients",
                    json={"pid": "P99", "name": "小明", "dob": "2015-01-01"})
    assert r.status_code == 201


def test_checkin(client):
    client.post("/api/home/patients",
                json={"pid": "P99", "name": "小明", "dob": "2015-01-01"})
    r = client.post("/api/home/checkin", json={
        "pid": "P99", "date": "2026-03-01", "temp": 39.2,
        "symptoms": {"乏力": True}})
    assert r.status_code == 200


def test_upload_commits_only_confirmed(client):
    client.post("/api/home/patients",
                json={"pid": "P99", "name": "小明", "dob": "2015-01-01"})
    r = client.post("/api/home/labs/upload", json={
        "pid": "P99", "date": "2026-03-01", "image_b64": "AAAA"})
    assert r.status_code == 200
    body = r.json()
    assert body["committed"] == 2
    review = [i for i in body["items"] if i["needs_review"]]
    assert [i["name"] for i in review] == ["血糖"]
    codes = {row[1] for row in
             client.store.rows("SELECT pid,code FROM lab WHERE pid='P99'")}
    assert codes == {"ferritin", "plt"}


def test_risk_returns_level_and_narration(client):
    client.post("/api/home/patients",
                json={"pid": "P99", "name": "小明", "dob": "2015-01-01"})
    client.post("/api/home/checkin", json={
        "pid": "P99", "date": "2026-03-01", "temp": 39.2, "symptoms": {}})
    client.post("/api/home/labs/upload", json={
        "pid": "P99", "date": "2026-03-01", "image_b64": "AAAA"})
    r = client.get("/api/home/risk/P99?as_of=2026-03-01")
    assert r.status_code == 200
    body = r.json()
    assert body["level"] in ("yellow", "red")
    assert body["score"] > 0
    assert "医生诊断" in body["text"]  # 免责声明渲染层追加
    assert body["meta"]["source"] in ("llm", "template", "blocked")
