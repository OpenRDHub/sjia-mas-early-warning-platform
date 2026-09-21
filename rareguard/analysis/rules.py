"""R-A 绝对阈值规则：纯确定性判定，不经 LLM。取值依据见 docs/references.md。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class RuleHit:
    rule_id: str
    name: str
    level: str  # yellow | red
    evidence: dict


def _latest(points):
    return points[-1] if points else None


# (id, code, 判定(value)->level|None, 名称)
_THRESHOLDS = [
    ("A1", "ferritin",
     lambda v: "red" if v >= 1000 else "yellow" if v >= 500 else None,
     "铁蛋白升高"),
    ("A2", "plt",
     lambda v: "red" if v < 50 else "yellow" if v < 100 else None,
     "血小板减少"),
    ("A3", "fib",
     lambda v: "red" if v < 1.0 else "yellow" if v < 1.5 else None,
     "纤维蛋白原降低"),
    ("A4", "alt",
     lambda v: "red" if v > 160 else "yellow" if v > 80 else None,
     "转氨酶升高"),
    ("A5", "tg",
     lambda v: "red" if v > 4.0 else "yellow" if v > 3.0 else None,
     "甘油三酯升高"),
]


def eval_absolute(series: dict, checkins: list) -> list:
    hits: list[RuleHit] = []
    for rule_id, code, check, name in _THRESHOLDS:
        p = _latest(series.get(code, []))
        if p is not None and (lv := check(p.value)):
            hits.append(RuleHit(rule_id, name, lv,
                                {"value": p.value, "date": p.date, "code": code}))
    if checkins and (c := checkins[-1]).temp is not None:
        lv = "red" if c.temp >= 39.0 else "yellow" if c.temp >= 38.5 else None
        if lv:
            hits.append(RuleHit("A6", "发热", lv,
                                {"value": c.temp, "date": c.date, "code": "temp"}))
    esr, crp = _latest(series.get("esr", [])), _latest(series.get("crp", []))
    if esr and crp and esr.value <= 10 and crp.value >= 30:
        hits.append(RuleHit("A7", "血沉-CRP分离", "red",
                            {"esr": esr.value, "crp": crp.value, "date": crp.date}))
    return hits
