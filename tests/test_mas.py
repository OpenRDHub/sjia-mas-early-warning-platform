from rareguard.data.store import Store
from rareguard.ts.provider import SqliteTimeSeries
from rareguard.analysis.mas import assess_patient, mas_score


def seed_mas_patient(s):
    s.add_patient("P05", "小红", "2013-03-02")
    for i, (fer, pl, fb, crp, esr, alt, tg, t) in enumerate([
        (320, 300, 3.4, 14, 30, 28, 1.3, 37.0),
        (400, 270, 3.1, 18, 26, 35, 1.6, 38.6),
        (520, 240, 2.7, 24, 20, 48, 2.1, 38.9),
        (700, 200, 2.2, 33, 14, 66, 2.7, 39.4),
        (950, 90, 1.3, 45, 9, 95, 3.4, 39.8),
    ]):
        d = f"2026-02-{10+i*2:02d}"
        for code, v, rl, rh in [("ferritin", fer, 7, 140), ("plt", pl, 150, 450),
                                 ("fib", fb, 2, 4), ("crp", crp, 0, 8),
                                 ("esr", esr, 0, 20), ("alt", alt, 0, 40),
                                 ("tg", tg, 0, 1.7)]:
            s.add_lab("P05", d, code, v, rl, rh)
        s.add_checkin("P05", d, t, {"fever": 1, "rash": 7})


def test_assess_patient_red(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    seed_mas_patient(s)
    a = assess_patient(SqliteTimeSeries(s), "P05", "2026-02-18")
    assert a.level == "red" and a.score >= 70
    s.close()


def test_green_patient(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.add_patient("P01", "小明", "2015-06-01")
    s.add_lab("P01", "2026-02-10", "ferritin", 120, 7, 140)
    s.add_checkin("P01", "2026-02-10", 36.7, {})
    a = assess_patient(SqliteTimeSeries(s), "P01", "2026-02-18")
    assert a.level == "green" and a.score == 0
    s.close()


def test_until_truncation(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    seed_mas_patient(s)
    ts = SqliteTimeSeries(s)
    early = assess_patient(ts, "P05", "2026-02-10")
    late = assess_patient(ts, "P05", "2026-02-18")
    assert early.score < late.score
    s.close()


def test_mas_score_detail_keys():
    _, detail = mas_score({}, [])
    assert set(detail) == {"fever", "ferritin", "plt", "fib", "alt",
                           "tg", "esr_crp_sep", "symptoms"}


def test_no_llm_import():
    import subprocess
    import sys
    r = subprocess.run(
        [sys.executable, "-c",
         "import rareguard.analysis.mas;"
         "import sys; assert not [x for x in sys.modules "
         "if 'rareguard.llm' in x]"],
        capture_output=True)
    assert r.returncode == 0
