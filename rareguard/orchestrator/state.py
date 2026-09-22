"""会话状态机（§4.1）：状态枚举 + 合法转移表 + 会话数据。

INIT → CONSENT → COLLECTING ⇄ PROBING → RETRIEVING → DRAFTING → REVIEW → DONE
                                    └── 任一采集时刻红旗旁路 → ALERT（红色）
状态由转移函数强制约束，非法转移抛 InvalidTransition 且不破坏当前状态。
P0a 状态存内存对象；持久化到数据库在 P0b 落地（§4.1 要求支持中断续答）。
"""

from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4


class SessionStatus(Enum):
    INIT = "init"
    CONSENT = "consent"
    COLLECTING = "collecting"
    PROBING = "probing"
    RETRIEVING = "retrieving"
    DRAFTING = "drafting"
    REVIEW = "review"
    DONE = "done"
    ALERT = "alert"


class InvalidTransition(Exception):
    pass


# 合法转移表（§4.1 状态图；ALERT 后转人工，会话以 DONE 收尾）
_TRANSITIONS: dict[SessionStatus, set[SessionStatus]] = {
    SessionStatus.INIT: {SessionStatus.CONSENT},
    SessionStatus.CONSENT: {SessionStatus.COLLECTING},
    SessionStatus.COLLECTING: {
        SessionStatus.PROBING, SessionStatus.RETRIEVING, SessionStatus.ALERT,
    },
    SessionStatus.PROBING: {
        SessionStatus.COLLECTING, SessionStatus.RETRIEVING, SessionStatus.ALERT,
    },
    SessionStatus.RETRIEVING: {SessionStatus.DRAFTING},
    SessionStatus.DRAFTING: {SessionStatus.REVIEW},
    SessionStatus.REVIEW: {SessionStatus.DONE},
    SessionStatus.DONE: set(),
    SessionStatus.ALERT: {SessionStatus.DONE},
}


@dataclass
class Session:
    session_id: str
    patient_id: str
    trace_id: str = field(default_factory=lambda: uuid4().hex)
    state: SessionStatus = SessionStatus.INIT
    slots: dict = field(default_factory=dict)  # N1 结构化槽位
    messages: list[dict] = field(default_factory=list)  # 对话历史
    risk_level: str = "none"  # none | yellow | red（只升不降）
    risk_rules: tuple[str, ...] = ()
    draft: str = ""
    pipeline_ok: bool = True  # 成文管道是否通过（False=草稿不可用）
    last_reply: str = ""
    review_notes: str = ""


def transition(session: Session, new_state: SessionStatus) -> None:
    """强制走合法转移；非法转移抛异常且保持原状态不变。"""
    if new_state not in _TRANSITIONS[session.state]:
        raise InvalidTransition(
            f"非法状态转移: {session.state.value} → {new_state.value}"
        )
    session.state = new_state
