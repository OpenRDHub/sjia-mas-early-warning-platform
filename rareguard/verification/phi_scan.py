"""L5 输出复审（P0a 基础版）：PHI/PII 泄露扫描。

身份证号命中 = SSN 级泄露，直接阻断；手机号命中 = 警告（放行但留痕）。
泄露值在 reason 中脱敏展示（§6.2：审计中患者标识不得明文）。
跨会话泄露比对与二次模型校验留待 P0b/P1。
"""

import re
from dataclasses import dataclass

_ID_CARD_RE = re.compile(
    r"(?<![0-9])[1-9]\d{5}(?:19|20)\d{2}"
    r"(?:0[1-9]|1[0-2])"
    r"(?:0[1-9]|[12]\d|3[01])"
    r"\d{3}[\dXx](?![0-9])"
)

_PHONE_RE = re.compile(r"(?<![0-9])1[3-9]\d{9}(?![0-9])")


@dataclass(frozen=True)
class ScanResult:
    ok: bool
    id_card_hits: int
    phone_hits: int
    reason: str = ""


def _mask(value: str) -> str:
    return value[:3] + "****" + value[-2:]


def scan_phi(text: str) -> ScanResult:
    """扫描输出文本中的 PII；身份证级命中即不通过（SSN 级阻断）。"""
    id_cards = _ID_CARD_RE.findall(text)
    phones = _PHONE_RE.findall(text)
    if id_cards:
        masked = ", ".join(_mask(v) for v in id_cards)
        return ScanResult(
            ok=False, id_card_hits=len(id_cards), phone_hits=len(phones),
            reason=f"身份证号泄露（SSN 级阻断）: {masked}",
        )
    if phones:
        masked = ", ".join(_mask(v) for v in phones)
        return ScanResult(
            ok=True, id_card_hits=0, phone_hits=len(phones),
            reason=f"手机号泄露（警告）: {masked}",
        )
    return ScanResult(ok=True, id_card_hits=0, phone_hits=0)
