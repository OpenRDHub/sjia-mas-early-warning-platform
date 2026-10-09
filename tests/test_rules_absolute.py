from rareguard.ts.provider import LabPoint, Checkin
from rareguard.analysis.rules import eval_absolute


def lp(code, date, v):
    return LabPoint(date, code, v, None, None)


def test_ferritin_yellow_and_red():
    s = {"ferritin": [lp("ferritin", "2026-01-08", 620)]}
    hits = eval_absolute(s, [])
    assert [h.level for h in hits if h.rule_id == "A1"] == ["yellow"]
    s = {"ferritin": [lp("ferritin", "2026-01-08", 1200)]}
    assert eval_absolute(s, [])[0].level == "red"


def test_esr_crp_dissociation_red():
    s = {"esr": [lp("esr", "2026-01-08", 8)], "crp": [lp("crp", "2026-01-08", 45)]}
    hits = eval_absolute(s, [])
    assert any(h.rule_id == "A7" and h.level == "red" for h in hits)


def test_fever_from_checkin():
    hits = eval_absolute({}, [Checkin("2026-01-08", 39.2, {})])
    assert hits and hits[0].rule_id == "A6" and hits[0].level == "red"


def test_normal_patient_no_hits():
    s = {"ferritin": [lp("ferritin", "2026-01-08", 120)],
         "plt": [lp("plt", "2026-01-08", 350)],
         "crp": [lp("crp", "2026-01-08", 8)]}
    assert eval_absolute(s, [Checkin("2026-01-08", 36.8, {})]) == []


def test_hit_carries_evidence():
    h = eval_absolute({"ferritin": [lp("ferritin", "2026-01-08", 1200)]}, [])[0]
    assert h.evidence["value"] == 1200 and h.evidence["date"] == "2026-01-08"
