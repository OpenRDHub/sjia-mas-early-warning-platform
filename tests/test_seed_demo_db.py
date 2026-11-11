import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from seed_demo_db import PID, seed  # noqa: E402

from rareguard.analysis.mas import assess_patient  # noqa: E402
from rareguard.data.store import Store  # noqa: E402
from rareguard.ts.provider import SqliteTimeSeries  # noqa: E402


def test_seed_gives_clean_green_yellow_red_escalation(tmp_path):
    info = seed(str(tmp_path / "demo.db"))
    assert info["pid"] == PID
    store = Store(info["db"])
    ts = SqliteTimeSeries(store)
    today = date.today()
    levels, scores = [], []
    for ago in (2, 1, 0):
        as_of = (today - timedelta(days=ago)).isoformat()
        a = assess_patient(ts, PID, as_of)
        levels.append(a.level)
        scores.append(a.score)
    store.close()
    assert levels == ["green", "yellow", "red"]
    assert scores == sorted(scores)  # 趋势线单调不降
    assert scores[-1] >= 70  # 末日为高危
