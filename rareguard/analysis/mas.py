"""R-C MAS 八项评分（HLH-2004 家庭可得分项简化）与 assess_patient 分级汇总。
确定性规则，禁止 import 任何 LLM 模块（产品红线）。"""
from dataclasses import dataclass

from rareguard.analysis.rules import eval_absolute, eval_2016
from rareguard.analysis.trends import eval_trend


@dataclass(frozen=True)
class Assessment:
    level: str  # green | yellow | red
    score: float
    hits: tuple


def _last(series, code):
    pts = series.get(code, [])
    return pts[-1].value if pts else None


def mas_score(series: dict, checkins: list) -> tuple:
    detail = {}
    fever_days = sum(1 for c in checkins[-7:] if (c.temp or 0) >= 38.5)
    detail["fever"] = 12.5 if fever_days >= 3 else 6.25 if fever_days >= 1 else 0.0

    def band(code, thr, invert=False):
        v = _last(series, code)
        if v is None:
            return 0.0
        return 12.5 if (v < thr if invert else v > thr) else 0.0

    detail["ferritin"] = band("ferritin", 500)
    detail["plt"] = band("plt", 100, invert=True)
    detail["fib"] = band("fib", 1.5, invert=True)
    detail["alt"] = band("alt", 80)
    detail["tg"] = band("tg", 3.0)
    esr, crp = _last(series, "esr"), _last(series, "crp")
    detail["esr_crp_sep"] = 12.5 if (esr is not None and crp is not None
                                     and esr <= 10 and crp >= 30) else 0.0
    sym = checkins[-1].symptoms if checkins else {}
    detail["symptoms"] = 12.5 if max(sym.get("rash", 0),
                                     sym.get("abdominal_pain", 0)) >= 5 else 0.0
    return round(sum(detail.values()), 2), detail


def assess_patient(ts, pid: str, as_of: str,
                   profile: str = "standard", min_criteria: int = 2) -> Assessment:
    codes = ts.codes(pid)
    series = {c: ts.get_lab_series(pid, c, until=as_of) for c in codes}
    checkins = ts.get_checkins(pid, until=as_of)
    hits = list(eval_absolute(series, checkins) + eval_trend(series))
    score, _ = mas_score(series, checkins)
    reds = sum(1 for h in hits if h.level == "red")
    level = ("red" if score >= 70 or reds >= 2
             else "yellow" if score >= 40 or hits else "green")
    if profile == "early":
        m16 = eval_2016(series, checkins, min_criteria=min_criteria)
        hits += m16
        if any(h.level == "red" for h in m16):
            level = "red"
        elif any(h.level == "yellow" for h in m16) and level == "green":
            level = "yellow"
    return Assessment(level=level, score=score, hits=tuple(hits))
