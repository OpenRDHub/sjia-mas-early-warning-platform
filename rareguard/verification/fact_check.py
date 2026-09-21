"""L3 事实接地（claim-check）：草稿数值断言必须有出处（§5 六层管道第三层）。

真实案例背景：模型曾为 EHR 仅有药名的"氯雷他定片"编造"10mg 每日一次"。
防线：草稿中所有 数字/中文数字 + 医学单位 组合，必须能在上下文
（患者口述槽位 + EHR 返回原文）中找到相同字面（空格归一化后比对）。
未接地 → needs_review=True 交医生人工复核（fail-safe 标记，不阻断）。
"""

import re
from dataclasses import dataclass, field

_UNITS = (
    r"(?:mg|μg|ug|ml|mmHg|mmol|g|kg|cm|mm|℃|°C|"
    r"片|粒|支|袋|喷|滴|贴|次|日|天|小时|分钟|周|月|年|度)"
)
_CLAIM_RE = re.compile(rf"[\d一二两三四五六七八九十百]+(?:\.\d+)?\s*{_UNITS}")


@dataclass(frozen=True)
class FactCheckResult:
    ok: bool = True
    needs_review: bool = False
    ungrounded: tuple = ()


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def extract_claims(text: str) -> list[str]:
    """提取草稿中所有 数值+单位 断言。"""
    return [m.group() for m in _CLAIM_RE.finditer(text)]


def check_grounded(draft: str, context: str) -> FactCheckResult:
    """校验草稿数值断言是否全部有出处。"""
    if not draft:
        return FactCheckResult()
    ctx = _norm(context or "")
    ungrounded = tuple(
        c for c in extract_claims(draft) if _norm(c) not in ctx
    )
    return FactCheckResult(
        ok=not ungrounded,
        needs_review=bool(ungrounded),
        ungrounded=ungrounded,
    )
