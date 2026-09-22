"""assess_patient 的 profile 参数：standard 默认零回归，early 叠加 2016 敏感档。"""
from rareguard.data.store import Store
from rareguard.ts.provider import SqliteTimeSeries
from rareguard.analysis.mas import assess_patient


def _seed_early_patient(store, pid="P100"):
    """铁蛋白900/plt150/ast60/高热：标准引擎判 yellow，2016 判据达标应 red。"""
    store.add_patient(pid, "小早", "2015-01-01")
    d = "2026-04-10"
    store.add_lab(pid, d, "ferritin", 900, 7, 140, "manual")
    store.add_lab(pid, d, "plt", 150, 125, 350, "manual")
    store.add_lab(pid, d, "ast", 60, 0, 40, "manual")
    store.add_checkin(pid, d, 39.2, {"fever": 1})


def test_early_profile_fires_when_standard_yellow(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    _seed_early_patient(s)
    ts = SqliteTimeSeries(s)
    std = assess_patient(ts, "P100", "2026-04-10")
    early = assess_patient(ts, "P100", "2026-04-10", profile="early")
    assert std.level == "yellow"
    assert not any(h.rule_id == "M16" for h in std.hits)
    assert any(h.rule_id == "M16" and h.level == "red" for h in early.hits)
    assert early.level == "red"
    s.close()


def test_early_profile_yellow_hint_single_secondary(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.add_patient("P101", "小早", "2015-01-01")
    d = "2026-04-10"
    s.add_lab("P101", d, "ferritin", 900, 7, 140, "manual")
    s.add_lab("P101", d, "plt", 150, 125, 350, "manual")  # 仅 1 项次要
    s.add_checkin("P101", d, 39.2, {"fever": 1})
    early = assess_patient(SqliteTimeSeries(s), "P101", "2026-04-10",
                           profile="early")
    m16 = [h for h in early.hits if h.rule_id == "M16"]
    assert m16 and m16[0].level == "yellow"
    s.close()


def test_default_equals_standard(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    _seed_early_patient(s)
    ts = SqliteTimeSeries(s)
    a = assess_patient(ts, "P100", "2026-04-10")
    b = assess_patient(ts, "P100", "2026-04-10", profile="standard")
    assert (a.level, a.score, [h.rule_id for h in a.hits]) == \
        (b.level, b.score, [h.rule_id for h in b.hits])
    s.close()


def test_early_never_downgrades(tmp_path):
    # 标准已 red 的病例（A1+A2 双红），early 不应降低等级/分数
    s = Store(str(tmp_path / "t.db"))
    s.add_patient("P102", "小重", "2015-01-01")
    d = "2026-04-10"
    s.add_lab("P102", d, "ferritin", 1200, 7, 140, "manual")
    s.add_lab("P102", d, "plt", 80, 125, 350, "manual")
    s.add_checkin("P102", d, 39.6, {"fever": 1})
    ts = SqliteTimeSeries(s)
    std = assess_patient(ts, "P102", "2026-04-10")
    early = assess_patient(ts, "P102", "2026-04-10", profile="early")
    assert std.level == "red"
    assert early.level == "red"
    assert early.score == std.score
    s.close()
