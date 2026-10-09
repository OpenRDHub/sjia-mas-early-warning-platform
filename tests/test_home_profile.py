"""家庭端 API 的 profile/min_criteria 查询参数透传。"""
from fastapi.testclient import TestClient

from rareguard.api.home import create_home_app
from rareguard.data.store import Store
from rareguard.llm.provider import BaseLLMProvider, LLMResponse


class _N(BaseLLMProvider):
    name = "n"

    def chat(self, messages, tools=None):
        return LLMResponse(text="建议尽快就诊，请以医生诊断为准。", model=self.name)


def _client(tmp_path):
    s = Store(str(tmp_path / "s.db"))
    s.add_patient("P100", "小早", "2015-01-01")
    d = "2026-04-10"
    s.add_lab("P100", d, "ferritin", 900, 7, 140, "manual")
    s.add_lab("P100", d, "plt", 150, 125, 350, "manual")
    s.add_lab("P100", d, "ast", 60, 0, 40, "manual")
    s.add_checkin("P100", d, 39.2, {"fever": 1})
    return TestClient(create_home_app(s, None, _N()))


def test_risk_default_is_standard(tmp_path):
    body = _client(tmp_path).get(
        "/api/home/risk/P100?as_of=2026-04-10").json()
    assert body["level"] == "yellow"
    assert not any(h["rule_id"] == "M16" for h in body["hits"])


def test_risk_early_profile_fires(tmp_path):
    body = _client(tmp_path).get(
        "/api/home/risk/P100?as_of=2026-04-10&profile=early").json()
    assert body["level"] == "red"
    assert any(h["rule_id"] == "M16" for h in body["hits"])


def test_trend_early_profile(tmp_path):
    client = _client(tmp_path)
    std = client.get("/api/home/trend/P100?as_of=2026-04-10&days=3").json()
    early = client.get(
        "/api/home/trend/P100?as_of=2026-04-10&days=3&profile=early").json()
    # 末日：standard=yellow，early=red
    assert std["points"][-1]["level"] == "yellow"
    assert early["points"][-1]["level"] == "red"


def test_summary_early_profile(tmp_path):
    body = _client(tmp_path).get(
        "/api/home/summary/P100?as_of=2026-04-10&profile=early").text
    assert "请以医生诊断为准" in body
