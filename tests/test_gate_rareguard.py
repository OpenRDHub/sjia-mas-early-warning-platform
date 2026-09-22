import datetime as dt
import pytest
from rareguard.data.store import Store
from rareguard.ts.provider import SqliteTimeSeries
from synth.generate_dataset import generate
from evals.gate_rareguard import gate_metrics


@pytest.fixture(scope="module")
def metrics(tmp_path_factory):
    s = Store(str(tmp_path_factory.mktemp("g") / "d.db"))
    generate(s, seed=42)
    m = gate_metrics(s)
    s.close()
    return m


def test_recall_100(metrics):
    assert metrics["recall"] == 1.0


def test_lead_at_least_48h(metrics):
    assert metrics["lead_hours_min"] >= 48


def test_false_alarm_rate(metrics):
    assert metrics["fp_episodes_per_pm"] <= 1.0
