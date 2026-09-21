"""红旗症状规则引擎：纯关键词规则匹配，独立通道，绝不经由大模型。"""

import json
from dataclasses import dataclass
from pathlib import Path

_DATA = Path(__file__).resolve().parents[1] / "data" / "redflag_rules.json"

_LEVEL_ORDER = {"none": 0, "yellow": 1, "red": 2}


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    level: str  # red | yellow
    groups: tuple[tuple[str, ...], ...]

    def matches(self, text: str) -> bool:
        return all(any(kw in text for kw in group) for group in self.groups)


@dataclass(frozen=True)
class RiskAssessment:
    level: str  # none | yellow | red
    matched: tuple[str, ...]


def load_default_rules(path: Path | None = None) -> list[Rule]:
    raw = json.loads((path or _DATA).read_text(encoding="utf-8"))
    return [
        Rule(
            id=r["id"],
            name=r["name"],
            level=r["level"],
            groups=tuple(tuple(g) for g in r["groups"]),
        )
        for r in raw
    ]


def assess(text: str, rules: list[Rule] | None = None) -> RiskAssessment:
    rules = rules if rules is not None else load_default_rules()
    matched = [r for r in rules if r.matches(text)]
    if not matched:
        return RiskAssessment(level="none", matched=())
    level = max((r.level for r in matched), key=lambda lv: _LEVEL_ORDER[lv])
    return RiskAssessment(level=level, matched=tuple(r.id for r in matched))
