"""会话存储：内存实现（开发默认）+ SQLite 持久化实现（§4.1 中断续答）。

两者接口一致，通过环境变量切换：
  MEDASSIST_STORE=sqlite MEDASSIST_DB_PATH=rareguard.db

SQLite 采用 WAL 模式，每操作独立连接（线程安全）；Session 序列化为
JSON 列，enum/tuple 等类型经显式转换恢复。
"""

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from rareguard.orchestrator.state import Session, SessionStatus


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dump_session(s: Session) -> str:
    """Session → JSON（enum/tuple 显式转换）。"""
    return json.dumps(
        {
            "session_id": s.session_id,
            "patient_id": s.patient_id,
            "trace_id": s.trace_id,
            "state": s.state.value,
            "slots": s.slots,
            "messages": s.messages,
            "risk_level": s.risk_level,
            "risk_rules": list(s.risk_rules),
            "draft": s.draft,
            "pipeline_ok": s.pipeline_ok,
            "last_reply": s.last_reply,
            "review_notes": s.review_notes,
        },
        ensure_ascii=False,
    )


def _load_session(data: str) -> Session:
    """JSON → Session（恢复 enum/tuple 类型）。"""
    d = json.loads(data)
    d["state"] = SessionStatus(d["state"])
    d["risk_rules"] = tuple(d["risk_rules"])
    return Session(**d)


class MemoryStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._alerts: list[dict] = []
        self._lock = threading.Lock()

    def save(self, s: Session) -> None:
        with self._lock:
            self._sessions[s.session_id] = s

    def get(self, sid: str) -> Session | None:
        return self._sessions.get(sid)

    def add_alert(self, alert: dict) -> None:
        with self._lock:
            self._alerts.append(alert)

    def alerts(self) -> list[dict]:
        return list(self._alerts)


class SqliteStore:
    """SQLite 持久化：服务重启后可恢复会话继续对话（中断续答）。"""

    def __init__(self, path: str | Path = "rareguard.db") -> None:
        self._path = str(path)
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def save(self, s: Session) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO sessions(session_id, data, updated_at) VALUES(?,?,?)"
                " ON CONFLICT(session_id) DO UPDATE SET data=excluded.data,"
                " updated_at=excluded.updated_at",
                (s.session_id, _dump_session(s), _utcnow()),
            )

    def get(self, sid: str) -> Session | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT data FROM sessions WHERE session_id=?", (sid,)
            ).fetchone()
        return _load_session(row[0]) if row else None

    def add_alert(self, alert: dict) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO alerts(data, created_at) VALUES(?,?)",
                (json.dumps(alert, ensure_ascii=False), _utcnow()),
            )

    def alerts(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT data FROM alerts ORDER BY id"
            ).fetchall()
        return [json.loads(r[0]) for r in rows]


def create_store() -> MemoryStore | SqliteStore:
    """按环境变量构建存储：默认内存，MEDASSIST_STORE=sqlite 切持久化。"""
    if os.environ.get("MEDASSIST_STORE", "").lower() == "sqlite":
        return SqliteStore(
            os.environ.get("MEDASSIST_DB_PATH", "rareguard.db")
        )
    return MemoryStore()
