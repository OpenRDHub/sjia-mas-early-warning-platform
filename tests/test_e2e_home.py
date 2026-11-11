import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from demo_e2e import demo_flow  # noqa: E402


def test_demo_flow_full_journey(tmp_path):
    out = demo_flow(str(tmp_path / "demo.db"))
    assert out["create_patient"] == 201
    assert out["checkins"] == [200, 200, 200]
    assert out["upload"]["committed"] == 3
    assert len(out["trend"]) == 7
    assert out["trend"][0]["score"] == 0.0
    assert out["trend"][-1]["score"] >= out["trend"][0]["score"]
    risk = out["risk"]
    assert risk["level"] == "red"
    assert risk["score"] >= 40
    assert risk["meta"]["source"] == "llm"
    assert "就诊" in risk["text"]
    assert "医生诊断" in risk["text"]
    assert out["manual"]["results"][0]["code"] == "tg"
