from rareguard.api.home import create_home_app
from rareguard.api.summary import latest_labs
from rareguard.data.store import Store
from rareguard.llm.provider import BaseLLMProvider, LLMResponse


class _N(BaseLLMProvider):
    name = "n"

    def chat(self, messages, tools=None):
        return LLMResponse(text="建议尽快就诊。", model=self.name)


def _store(tmp_path):
    store = Store(str(tmp_path / "s.db"))
    store.add_patient("P01", "小明", "2016-05-01")
    store.add_lab("P01", "2026-03-04", "ferritin", 200, 15, 150, "manual")
    store.add_lab("P01", "2026-03-05", "ferritin", 1200, 15, 150, "manual")
    store.add_lab("P01", "2026-03-05", "plt", 80, 125, 350, "manual")
    return store


def test_latest_labs_picks_recent_and_flags_abnormal(tmp_path):
    labs = latest_labs(_store(tmp_path), "P01", "2026-03-05")
    ferr = next(l for l in labs if l["code"] == "ferritin")
    assert ferr["value"] == 1200 and ferr["abnormal"]
    assert all(l["abnormal"] for l in labs if l["code"] == "plt")


def test_summary_page_renders(tmp_path):
    from fastapi.testclient import TestClient

    client = TestClient(create_home_app(_store(tmp_path), None, _N()))
    body = client.get(
        "/api/home/summary/P01?as_of=2026-03-05").text
    assert "小明" in body
    assert "血清铁蛋白" in body
    assert "1200" in body
    assert "请以医生诊断为准" in body


def test_summary_has_no_external_urls(tmp_path):
    from fastapi.testclient import TestClient

    client = TestClient(create_home_app(_store(tmp_path), None, _N()))
    body = client.get(
        "/api/home/summary/P01?as_of=2026-03-05").text
    assert "http://" not in body and "https://" not in body
