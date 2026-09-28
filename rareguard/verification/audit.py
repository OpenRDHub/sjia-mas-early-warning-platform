"""L6 审计日志：全链路留痕，fail-closed（记录失败 = 阻断响应）。

写入/序列化失败直接抛出，由调用方（验证管道）将响应阻断——
宁可服务不可用，不可不留痕（§5 L6）。

双后端：
  - JSONL 追加写（默认，开发/测试）
  - SQLite 独立审计库：MEDASSIST_AUDIT_DB=audit.db 或显式传 db 参数
    （P0b 院内部署用独立实例/账号；表级 WORM 触发器禁止 UPDATE/DELETE）
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_AUDIT_PATH = Path("audit_log.jsonl")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    trace_id TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL DEFAULT '',
    event TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_trace ON audit_events(trace_id);
CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_events(event_type);
CREATE TRIGGER IF NOT EXISTS audit_worm_no_update
BEFORE UPDATE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit is write-once');
END;
CREATE TRIGGER IF NOT EXISTS audit_worm_no_delete
BEFORE DELETE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit is write-once');
END;
"""


class SqliteAuditBackend:
    """独立 SQLite 审计库：append-only（WORM 触发器级禁改禁删）。"""

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def log(self, record: dict) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO audit_events(ts, trace_id, event_type, event)"
                " VALUES(?,?,?,?)",
                (
                    record["ts"],
                    record.get("trace_id", ""),
                    record.get("event", ""),
                    json.dumps(record, ensure_ascii=False),
                ),
            )

    def query(
        self,
        trace_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """只读查询（合规审查/可观测性）。"""
        sql, args = "SELECT event FROM audit_events", []
        if trace_id:
            sql += " WHERE trace_id=?"
            args.append(trace_id)
        if event_type:
            sql += (" AND" if trace_id else " WHERE") + " event_type=?"
            args.append(event_type)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self._conn() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [json.loads(r[0]) for r in rows]


def log_event(
    event: dict,
    path: Path | None = None,
    db: "str | Path | SqliteAuditBackend | None" = None,
) -> None:
    """追加一条审计事件；任何失败都抛异常（fail-closed），绝不静默丢弃。

    后端优先级：显式 db > 显式 path > 环境变量 MEDASSIST_AUDIT_DB > 默认 JSONL。
    """
    record = {"ts": datetime.now(timezone.utc).isoformat(), **event}
    if isinstance(db, SqliteAuditBackend):
        db.log(record)
        return
    db_path = db if db is not None else os.environ.get("MEDASSIST_AUDIT_DB")
    if db_path:
        _env_backend(db_path).log(record)
        return
    target = path if path is not None else DEFAULT_AUDIT_PATH
    line = json.dumps(record, ensure_ascii=False)
    with target.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()


_ENV_BACKENDS: dict[str, SqliteAuditBackend] = {}


def _env_backend(db_path: "str | Path") -> SqliteAuditBackend:
    """环境变量后端缓存（避免每条事件重建连接/建表）。"""
    key = str(db_path)
    if key not in _ENV_BACKENDS:
        _ENV_BACKENDS[key] = SqliteAuditBackend(key)
    return _ENV_BACKENDS[key]
