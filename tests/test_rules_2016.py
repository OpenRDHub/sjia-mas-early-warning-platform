"""2016 PRINTO/ACR/EULAR sJIA-MAS 分类判据（附加敏感档）。

红线：纯确定性判定，禁止 import LLM。取值依据见 docs/references.md。
标准：发热 + 铁蛋白>684 ng/mL + ≥min_criteria 项次要指标
  核心：PLT≤181×10⁹/L、AST>48 U/L；一般：TG>156mg/dL(1.76mmol/L)、FIB≤3.6 g/L。
"""
from rareguard.ts.provider import LabPoint, Checkin
from rareguard.analysis.rules import eval_2016


def lp(code, v, date="2026-03-01"):
    return LabPoint(date, code, v, None, None)


def s(**kv):
    return {c: [lp(c, v)] for c, v in kv.items()}


FEB = [Checkin("2026-03-01", 39.0, {})]


def _m16(hits):
    return [h for h in hits if h.rule_id == "M16"]


def test_meets_2016_red_two_core():
    hits = eval_2016(s(ferritin=900, plt=150, ast=60), FEB)
    assert _m16(hits) and _m16(hits)[0].level == "red"


def test_no_fever_no_hit():
    assert eval_2016(s(ferritin=900, plt=150, ast=60), []) == []
    assert eval_2016(s(ferritin=900, plt=150, ast=60),
                     [Checkin("2026-03-01", 37.5, {})]) == []


def test_ferritin_gate():
    # 铁蛋白 <=684 不触发
    assert eval_2016(s(ferritin=600, plt=150, ast=60), FEB) == []
    # 缺铁蛋白也不触发
    assert eval_2016(s(plt=150, ast=60), FEB) == []


def test_single_secondary_yellow():
    hits = eval_2016(s(ferritin=900, plt=150), FEB)
    assert _m16(hits)[0].level == "yellow"


def test_zero_secondary_no_hit():
    assert eval_2016(s(ferritin=900, plt=300, ast=20, tg=1.0, fib=4.5), FEB) == []


def test_general_secondary_meets():
    # TG>1.76 且 FIB<=3.6 两项一般指标 => 达标 red
    hits = eval_2016(s(ferritin=900, tg=1.8, fib=3.5), FEB)
    assert _m16(hits)[0].level == "red"


def test_core_general_tagging():
    h = _m16(eval_2016(s(ferritin=900, plt=150, ast=60, tg=2.5, fib=3.0), FEB))[0]
    assert h.evidence["met_core"] == 2 and h.evidence["met_general"] == 2
    assert set(h.evidence["met"]) == {"plt", "ast", "tg", "fib"}


def test_sensitivity_knob_min_criteria_1():
    hits = eval_2016(s(ferritin=900, plt=150), FEB, min_criteria=1)
    assert _m16(hits)[0].level == "red"


def test_boundary_values():
    # plt 恰 181 计入；ast 恰 48 不计入（严格>）；fib 恰 3.6 计入（<=）
    assert _m16(eval_2016(s(ferritin=900, plt=181, fib=3.6), FEB))[0].level == "red"
    assert eval_2016(s(ferritin=900, ast=48), FEB) == []  # 仅0项，ast=48不计
