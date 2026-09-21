"""L4 医疗护栏：确诊句式 / 处方句式 / 剂量推荐规则库拦截（红线 R1/R2）。

命中即整段替换为兜底文案并标记人工复核（needs_review）；
保守策略：宁可误拦，不可漏放，模式库随评测集迭代调优。
P0a 阶段以中文句式为主，英文句式待评测集扩充后补齐。
"""

import re
from dataclasses import dataclass

FALLBACK_TEXT = "本段内容已按平台医疗安全规范拦截（可能包含诊断或处方类信息）。请以执业医师面诊结论为准。"

# 确诊类句式（R1：禁止输出确诊结论）；[你您] 兼容敬称
_DIAGNOSIS_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p)
    for p in (
        r"[你您]得了", r"[你您]患了", r"[你您]患有", r"[你您]这是",
        r"诊断为", r"确诊为", r"可以确诊", r"基本确诊", r"明确确诊",
        r"确定是", r"就是得了",
    )
)

# 处方/用药建议类句式（R2：禁止输出处方或用药方案）
_PRESCRIPTION_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p)
    for p in (
        r"建议服用", r"建议使用", r"建议口服", r"建议应用", r"建议吃",
        r"可以服用", r"可以口服", r"可以吃", r"可以使用",
        r"推荐服用", r"推荐使用", r"推荐口服",
        r"需要服用", r"需要口服", r"需要使用",
        r"应该服用", r"应当服用", r"应该口服", r"要服用",
        r"给[你您]开", r"开一些", r"开点",
        r"处方如下", r"处方：", r"用药方案",
    )
)

# 剂量推荐：数字（含中文数字，注意"两"）+ 剂量单位
_DOSAGE_RE = re.compile(
    r"[0-9０-９一两二三四五六七八九十]+(?:\.[0-9]+)?\s*"
    r"(?:毫克|μg|ug|mg|ml|iu|毫升|克|g|片|粒|支|喷|滴)"
)

# 频次词：与剂量单位同时出现才判定为剂量推荐
_FREQ_RE = re.compile(
    r"每日|每天|一日|每次|隔日|隔天|睡前|一天|bid|tid|qid|q8h|每8小时",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    text: str
    reason: str = ""
    needs_review: bool = False


def check_output(text: str) -> GuardResult:
    """对 LLM 输出做医疗护栏校验；命中即整段替换为兜底文案并标记人工复核。"""
    for pattern in _DIAGNOSIS_PATTERNS:
        if pattern.search(text):
            return GuardResult(
                ok=False, text=FALLBACK_TEXT,
                reason=f"确诊类句式（命中: {pattern.pattern}）", needs_review=True,
            )
    for pattern in _PRESCRIPTION_PATTERNS:
        if pattern.search(text):
            return GuardResult(
                ok=False, text=FALLBACK_TEXT,
                reason=f"处方类句式（命中: {pattern.pattern}）", needs_review=True,
            )
    if _DOSAGE_RE.search(text) and _FREQ_RE.search(text):
        dosage = _DOSAGE_RE.search(text).group()
        return GuardResult(
            ok=False, text=FALLBACK_TEXT,
            reason=f"剂量推荐（命中: {dosage.strip()}）", needs_review=True,
        )
    return GuardResult(ok=True, text=text)
