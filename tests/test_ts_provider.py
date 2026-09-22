from rareguard.data.store import Store
from rareguard.ts.provider import (
    SqliteTimeSeries, TimeSeriesProvider, LabPoint, Checkin)


def make(store):
    store.add_patient("P01", "小明", "2015-06-01")
    store.add_lab("P01", "2026-01-08", "crp", 30.0, 0, 5)
    store.add_lab("P01", "2026-01-01", "crp", 12.0, 0, 5)
    store.add_lab("P01", "2026-01-15", "crp", 45.0, 0, 5)
    store.add_checkin("P01", "2026-01-08", 38.7, {"fever": 1})


def test_series_sorted_and_filtered(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    make(s)
    ts = SqliteTimeSeries(s)
    pts = ts.get_lab_series("P01", "crp", until="2026-01-08")
    assert [p.date for p in pts] == ["2026-01-01", "2026-01-08"]
    assert pts[1] == LabPoint("2026-01-08", "crp", 30.0, 0, 5)
    s.close()


def test_checkins_deserialize(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    make(s)
    ts = SqliteTimeSeries(s)
    assert ts.get_checkins("P01")[0] == Checkin("2026-01-08", 38.7, {"fever": 1})
    s.close()


def test_codes_distinct(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    make(s)
    s.add_lab("P01", "2026-01-08", "plt", 300.0, 150, 450)
    ts = SqliteTimeSeries(s)
    assert ts.codes("P01") == ["crp", "plt"]
    s.close()


def test_provider_has_no_write_methods():
    assert not [m for m in dir(TimeSeriesProvider)
                if m.startswith(("add_", "write_", "set_"))]
