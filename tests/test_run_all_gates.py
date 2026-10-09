import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from run_all_gates import GATE_STEPS  # noqa: E402


def test_gate_plan_covers_five_gates():
    labels = {s["label"] for s in GATE_STEPS}
    assert {"w1-metrics", "ocr-synthetic", "redline-gate",
            "offline-e2e", "real-smoke"} <= labels
    net = {s["label"] for s in GATE_STEPS if s.get("requires_net")}
    assert net == {"real-smoke"}


def test_all_steps_have_argv_list():
    assert all(isinstance(s["argv"], list) and s["argv"] for s in GATE_STEPS)
