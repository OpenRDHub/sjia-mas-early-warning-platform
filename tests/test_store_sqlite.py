"""SQLite 持久化测试：Session 往返等价、重启续答（§4.1）、告警持久化。"""

from rareguard.api.store import MemoryStore, SqliteStore
from rareguard.ehr.mock_provider import MockEHRProvider
from rareguard.llm.mock_provider import MockLLMProvider
from rareguard.orchestrator.graph import (
    handle_patient_input,
    sign_consent,
    start_session,
)
from rareguard.orchestrator.state import SessionStatus


def _mk_session():
    return start_session("S-test", "P001")


def test_session_roundtrip(tmp_path):
    """各字段（含 ALERT 态/tuple/enum/嵌套 dict）往返等价。"""
    db = tmp_path / "s.db"
    s = _mk_session()
    sign_consent(s)
    s.messages = [{"role": "user", "content": "我胸口疼"}]
    s.slots = {"chief_complaint": "胸口疼", "severity": "严重"}
    s.risk_level, s.risk_rules = "yellow", ("RF002",)
    s.last_reply = "请问持续多久了？"
    SqliteStore(db).save(s)

    # 新实例模拟重启
    restored = SqliteStore(db).get(s.session_id)
    assert restored is not None
    assert restored.patient_id == s.patient_id
    assert restored.trace_id == s.trace_id
    assert restored.state == SessionStatus.COLLECTING
    assert restored.messages == s.messages
    assert restored.slots == s.slots
    assert restored.risk_rules == ("RF002",)  # tuple 类型恢复
    assert restored.risk_level == "yellow"
    assert restored.last_reply == s.last_reply

    assert SqliteStore(db).get("S-none") is None


def test_resume_after_restart(tmp_path):
    """核心验收：中断后重启，患者续答走完全流程。"""
    db = tmp_path / "s.db"
    s1 = SqliteStore(db)
    s = _mk_session()
    sign_consent(s)
    s = handle_patient_input(s, "我胸口疼", MockLLMProvider(), ehr=MockEHRProvider())
    s1.save(s)  # 中断（服务重启）

    # 新实例恢复，继续第二轮对话
    s2 = SqliteStore(db)
    s = s2.get(s.session_id)
    assert s.state == SessionStatus.COLLECTING
    s = handle_patient_input(s, "疼了三天了", MockLLMProvider(), ehr=MockEHRProvider())
    s2.save(s)
    assert s.state == SessionStatus.REVIEW
    assert "青霉素" in s.draft and s.pipeline_ok


def test_alerts_persist(tmp_path):
    """告警队列重启不丢（护士站审计要求）。"""
    db = tmp_path / "s.db"
    s1 = SqliteStore(db)
    s1.add_alert({"session_id": "S-1", "risk_rules": ["RF007"]})
    s1.add_alert({"session_id": "S-2", "risk_rules": ["RF004"]})

    restored = SqliteStore(db).alerts()
    assert [a["session_id"] for a in restored] == ["S-1", "S-2"]


def test_stores_interface_compatible(tmp_path):
    """MemoryStore / SqliteStore 接口行为一致（save/get/alerts 可互换）。"""
    for store in (MemoryStore(), SqliteStore(tmp_path / "m.db")):
        s = _mk_session()
        store.save(s)
        assert store.get(s.session_id).session_id == s.session_id
        store.add_alert({"x": 1})
        assert len(store.alerts()) == 1
