import datetime as dt
from rareguard.data.store import Store
from rareguard.ts.provider import SqliteTimeSeries
from rareguard.analysis.mas import assess_patient
from synth.generate_dataset import generate, START, DAYS


def test_generate_shape(tmp_path):
    s = Store(str(tmp_path / "d.db"))
    kinds = generate(s, seed=42)
    assert sorted(kinds) == [f"P0{i}" for i in range(1, 7)]
    assert list(kinds.values()).count("mas") == 2
    labs = s.rows("SELECT COUNT(*) FROM lab", ())[0][0]
    assert labs > 6 * 90 * 6
    s.close()


def test_deterministic(tmp_path):
    a = Store(str(tmp_path / "a.db"))
    b = Store(str(tmp_path / "b.db"))
    generate(a, seed=42)
    generate(b, seed=42)
    ra = a.rows("SELECT pid,date,code,value FROM lab ORDER BY pid,date,code", ())
    rb = b.rows("SELECT pid,date,code,value FROM lab ORDER BY pid,date,code", ())
    assert ra == rb
    a.close()
    b.close()


def test_normal_patients_never_red(tmp_path):
    s = Store(str(tmp_path / "d.db"))
    generate(s, seed=42)
    ts = SqliteTimeSeries(s)
    for pid in ["P01", "P02", "P03", "P04"]:
        for day in range(0, DAYS, 10):
            d = (START + dt.timedelta(days=day)).isoformat()
            a = assess_patient(ts, pid, d)
            assert a.level != "red", (pid, d, a.score, a.hits)
    s.close()
