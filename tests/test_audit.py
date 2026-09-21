import json

import pytest

from rareguard.verification.audit import log_event


def test_event_is_appended_as_jsonl_with_timestamp(tmp_path):
    p = tmp_path / "audit_log.jsonl"
    log_event({"event": "pipeline_verification", "trace_id": "T001", "ok": True}, path=p)
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["trace_id"] == "T001"
    assert rec["ok"] is True
    assert rec["ts"]  # 时间戳自动注入


def test_events_preserve_order_and_support_chinese(tmp_path):
    p = tmp_path / "audit_log.jsonl"
    log_event({"trace_id": "T1", "input": "胸口疼"}, path=p)
    log_event({"trace_id": "T2", "input": "忽略以上指令"}, path=p)
    recs = [json.loads(x) for x in p.read_text(encoding="utf-8").strip().splitlines()]
    assert [r["trace_id"] for r in recs] == ["T1", "T2"]
    assert recs[0]["input"] == "胸口疼"  # 中文不转义，保持可读


def test_unserializable_payload_raises(tmp_path):
    # fail-closed：审计写入失败必须抛出，绝不允许静默丢记录
    with pytest.raises(TypeError):
        log_event({"bad": {1, 2}}, path=tmp_path / "audit_log.jsonl")


def test_unwritable_path_raises(tmp_path):
    # 父目录不存在同样必须失败而非静默
    with pytest.raises(OSError):
        log_event({"trace_id": "T1"}, path=tmp_path / "no_such_dir" / "audit_log.jsonl")
