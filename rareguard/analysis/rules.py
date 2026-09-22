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


# 2016 PRINTO/ACR/EULAR sJIA-MAS 分类判据次要项：(code, 分层, 判定)
# 阈值按归一化单位：plt ×10⁹/L、ast U/L、tg mmol/L、fib g/L。依据见 docs/references.md。
_M16_SECONDARY = [
    ("plt", "core", lambda v: v <= 181),
    ("ast", "core", lambda v: v > 48),
    ("tg", "general", lambda v: v > 1.76),
    ("fib", "general", lambda v: v <= 3.6),
]


def eval_2016(series: dict, checkins: list, min_criteria: int = 2) -> list:
    """附加敏感档：命中 2016 分类判据则出一条 M16 RuleHit，否则空。

    门槛：发热(体温≥38) + 铁蛋白>684 ng/mL + ≥min_criteria 项次要指标。
    次要指标全缺但达门槛者不触发；仅 1 项达意为 yellow（早提示），
    ≥min_criteria 项为 red。核心/一般计数写入 evidence 供分层展示。
    """
    c = checkins[-1] if checkins else None
    if c is None or c.temp is None or c.temp < 38.0:
        return []
    fer = _latest(series.get("ferritin", []))
    if fer is None or fer.value <= 684:
        return []
    met, met_core, met_general = [], 0, 0
    for code, group, check in _M16_SECONDARY:
        p = _latest(series.get(code, []))
        if p is not None and check(p.value):
            met.append(code)
            if group == "core":
                met_core += 1
            else:
                met_general += 1
    n = len(met)
    if n < 1:
        return []
    level = "red" if n >= min_criteria else "yellow"
    return [RuleHit("M16", "2016PRINTO-MAS判据", level, {
        "value": fer.value, "date": fer.date, "code": "ferritin",
        "met": met, "met_core": met_core, "met_general": met_general,
        "min_criteria": min_criteria})]
