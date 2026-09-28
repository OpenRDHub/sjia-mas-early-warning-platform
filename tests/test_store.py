import json
import pytest
from rareguard.data.store import Store


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    yield s
    s.close()


def test_add_and_query_lab(store):
    store.add_patient("P01", "小明", "2015-06-01")
    store.add_lab("P01", "2026-01-08", "ferritin", 620.0, 23.9, 336.2)
    rows = store.rows(
        "SELECT date, code, value FROM lab WHERE pid=? ORDER BY date", ("P01",))
    assert rows == [("2026-01-08", "ferritin", 620.0)]


def test_add_lab_upserts(store):
    store.add_patient("P01", "小明", "2015-06-01")
    store.add_lab("P01", "2026-01-08", "crp", 30.0, 0, 5)
    store.add_lab("P01", "2026-01-08", "crp", 33.0, 0, 5)
    assert store.rows("SELECT value FROM lab", ())[0][0] == 33.0


def test_add_checkin_serializes_symptoms(store):
    store.add_patient("P01", "小明", "2015-06-01")
    store.add_checkin("P01", "2026-01-08", 38.7, {"fever": 1, "rash": 6})
    raw = store.rows("SELECT temp, symptoms FROM checkin", ())[0]
    assert raw[0] == 38.7 and json.loads(raw[1]) == {"fever": 1, "rash": 6}
