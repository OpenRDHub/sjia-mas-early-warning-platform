"""T5 审计库测试：SQLite 独立后端（WORM）、fail-closed、环境变量切换。"""

import sqlite3

import pytest

from rareguard.verification.audit import SqliteAuditBackend, log_event


def test_sqlite_write_and_query(tmp_path):
    db = SqliteAuditBackend(tmp_path / "audit.db")
    log_event({"event": "pipeline_verification", "trace_id": "T1", "ok": True}, db=db)
    log_event({"event": "risk_alert", "trace_id": "T2"}, db=db)

    events = db.query()
    assert len(events) == 2
    assert events[0]["trace_id"] == "T2"  # 最新在前
    by_trace = db.query(trace_id="T1")
    assert len(by_trace) == 1 and by_trace[0]["ok"] is True
    by_type = db.query(event_type="risk_alert")
    assert len(by_type) == 1


def test_worm_no_update_no_delete(tmp_path):
    """WORM 语义：触发器级禁止改/删（代码无法绕过）。"""
    db = SqliteAuditBackend(tmp_path / "audit.db")
    log_event({"event": "e", "trace_id": "T1"}, db=db)
    conn = sqlite3.connect(tmp_path / "audit.db")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE audit_events SET event='{}'")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM audit_events")
    conn.close()


def test_fail_closed_on_bad_backend(tmp_path):
    """fail-closed：写入失败必须抛异常（由管道转阻断）。"""
    # 目录路径当 db 文件 → 无法建表
    d = tmp_path / "dir.db"
    d.mkdir()
    with pytest.raises(Exception):
        SqliteAuditBackend(d)


def test_env_var_switches_backend(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDASSIST_AUDIT_DB", str(tmp_path / "env.db"))
    log_event({"event": "e", "trace_id": "TE"})  # 不传 path/db
    log_event({"event": "e2", "trace_id": "TE"})
    backend = SqliteAuditBackend(tmp_path / "env.db")
    assert len(backend.query(trace_id="TE")) == 2


def test_jsonl_default_unchanged(tmp_path):
    """默认 JSONL 行为不变（现有调用零破坏）。"""
    p = tmp_path / "a.jsonl"
    log_event({"event": "e", "trace_id": "TJ"}, path=p)
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1 and '"TJ"' in lines[0]


def test_independent_from_business_db(tmp_path):
    """审计库与业务会话库是独立文件（独立实例/账号语义）。"""
    audit = tmp_path / "audit.db"
    business = tmp_path / "rareguard.db"
    log_event({"event": "e", "trace_id": "TI"}, db=audit)
    business.write_text("business", encoding="utf-8")
    conn = sqlite3.connect(audit)
    tables = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    conn.close()
    assert "audit_events" in tables and "sessions" not in tables
