from rareguard.ts.provider import LabPoint
from rareguard.analysis.trends import eval_trend


def lp(code, date, v):
    return LabPoint(date, code, v, None, None)


def series(code, vals):
    return {code: [lp(code, f"2026-01-{i+1:02d}", v)
                   for i, v in enumerate(vals)]}


def test_crp_rising_triggers_b1():
    hits = eval_trend(series("crp", [12, 18, 32]))
    assert [h.rule_id for h in hits] == ["B1"] and hits[0].level == "yellow"


def test_noise_does_not_trigger():
    assert eval_trend(series("crp", [12.0, 12.4, 12.1])) == []
    assert eval_trend(series("crp", [8, 10, 11.4])) == []  # 末值未到 30


def test_ferritin_doubling_is_red_b5():
    s = {"ferritin": [lp("ferritin", "2026-01-01", 300),
                      lp("ferritin", "2026-01-12", 660)]}
    ids = {h.rule_id for h in eval_trend(s)}
    assert "B5" in ids


def test_plt_fib_cooldown_is_red_b4():
    s = {"plt": [lp("plt", f"2026-01-{i+1:02d}", v)
                 for i, v in enumerate([220, 190, 160])],
         "fib": [lp("fib", f"2026-01-{i+1:02d}", v)
                 for i, v in enumerate([3.2, 2.6, 2.0])]}
    hits = eval_trend(s)
    assert any(h.rule_id == "B4" and h.level == "red" for h in hits)


def test_plt_slow_decline_b3():
    hits = eval_trend(series("plt", [190, 170, 145]))
    assert any(h.rule_id == "B3" and h.level == "yellow" for h in hits)
