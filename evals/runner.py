"""评测执行器（§7）：数据驱动用例集 + 指标汇总。

红旗必测集漏报 = 发布阻断（§7.2：红旗召回率必须 100%）；
P0a 门禁：全部用例在 Mock 数据上通过（Mock Provider + Mock EHR）。
用例为 JSONL，位于 evals/cases/，模型/提示词/知识库任一变更后全量重跑。
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from rareguard.ehr.mock_provider import MockEHRProvider
from rareguard.llm.mock_provider import MockLLMProvider
from rareguard.orchestrator.graph import (
    handle_patient_input,
    sign_consent,
    start_session,
)
from rareguard.risk.rules import assess
from rareguard.verification.input_guard import check_input
from rareguard.verification.medical_guard import check_output

_CASES_DIR = Path(__file__).resolve().parent / "cases"


@dataclass
class CaseResult:
    case_id: str
    passed: bool
    detail: str = ""


@dataclass
class EvalReport:
    category: str
    results: list[CaseResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failures(self) -> list[CaseResult]:
        return [r for r in self.results if not r.passed]

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 1.0

    def summary(self) -> str:
        lines = [
            f"[{self.category}] {self.passed}/{self.total} 通过"
            f"（{self.pass_rate:.0%}）"
        ]
        lines += [f"  FAIL {r.case_id}: {r.detail}" for r in self.failures]
        return "\n".join(lines)


def load_cases(name: str) -> list[dict]:
    path = _CASES_DIR / f"{name}.jsonl"
    return [
        json.loads(x)
        for x in path.read_text(encoding="utf-8").strip().splitlines()
        if x.strip()
    ]


def run_redflag_cases(cases: list[dict]) -> EvalReport:
    """红旗必测：期望等级与命中规则逐一比对；漏报即失败。"""
    report = EvalReport(category="redflag")
    for c in cases:
        ra = assess(c["text"])
        ok = ra.level == c["expect_level"]
        if ok and c.get("expect_rules"):
            ok = set(c["expect_rules"]) <= set(ra.matched)
        detail = (
            "" if ok
            else f"期望 {c['expect_level']} {c.get('expect_rules', '')}，"
                 f"实际 {ra.level} {list(ra.matched)}"
        )
        report.results.append(CaseResult(c["id"], ok, detail))
    return report


def run_injection_cases(cases: list[dict]) -> EvalReport:
    """对抗注入：L1 必须拦截（§7.2：拦截率门禁）。"""
    report = EvalReport(category="injection")
    for c in cases:
        v = check_input(c["text"])
        blocked = not v.ok
        ok = blocked if c["expect"] == "blocked" else not blocked
        detail = (
            "" if ok
            else f"期望 {c['expect']}，实际 {'blocked' if blocked else 'passed'}"
                 f"（{v.reason}）"
        )
        report.results.append(CaseResult(c["id"], ok, detail))
    return report


def run_guard_cases(cases: list[dict]) -> EvalReport:
    """L4 医疗护栏：确诊/处方/剂量必须拦截，正常文书放行。"""
    report = EvalReport(category="guard")
    for c in cases:
        g = check_output(c["text"])
        blocked = not g.ok
        ok = blocked if c["expect"] == "blocked" else not blocked
        detail = (
            "" if ok
            else f"期望 {c['expect']}，实际 {'blocked' if blocked else 'passed'}"
                 f"（{g.reason}）"
        )
        report.results.append(CaseResult(c["id"], ok, detail))
    return report


def run_normal_cases(cases: list[dict], llm=None, ehr=None) -> EvalReport:
    """正常路径全流程：编排状态机走通主链路（默认 Mock，可注入真实 Provider）。"""
    report = EvalReport(category="normal")
    for c in cases:
        try:
            llm = llm or MockLLMProvider()
            ehr = ehr or MockEHRProvider()
            s = start_session(f"eval-{c['id']}", c.get("patient_id", "P001"))
            sign_consent(s)
            for text in c["inputs"]:
                s = handle_patient_input(s, text, llm, ehr=ehr)
            ok = (
                s.state.value == c.get("expect_final_state", "review")
                and s.pipeline_ok
                and bool(s.draft)
            )
            missing = [
                k for k in c.get("expect_draft_contains", []) if k not in s.draft
            ]
            ok = ok and not missing
            detail = (
                "" if ok
                else f"状态 {s.state.value}，pipeline_ok={s.pipeline_ok}，"
                     f"缺失片段 {missing}"
            )
        except Exception as exc:  # 评测把异常计为失败而非中断
            ok, detail = False, f"异常: {type(exc).__name__}: {exc}"
        report.results.append(CaseResult(c["id"], ok, detail))
    return report
