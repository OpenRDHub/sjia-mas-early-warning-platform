"""W1 评测门禁：MAS 召回 100% / 提前量 ≥48h / 误报 ≤1 次·患者·月。

门禁不达标 = 阻断发布（调规则参数须在 docs/references.md 登记依据，禁改测试）。
"""
import datetime as dt

from rareguard.ts.provider import SqliteTimeSeries
from rareguard.analysis.mas import assess_patient
from synth.generate_dataset import START, DAYS


def run_assessments(ts, pid):
    out = []
    for day in range(DAYS):
        d = (START + dt.timedelta(days=day)).isoformat()
        out.append((d, assess_patient(ts, pid, d)))
    return out


def _episodes(alert_days):
    """连续预警日计为 1 次 episode。"""
    return sum(1 for i, d in enumerate(alert_days)
               if i == 0 or (dt.date.fromisoformat(d)
                             - dt.date.fromisoformat(alert_days[i - 1])).days > 1)


def gate_metrics(store):
    ts = SqliteTimeSeries(store)
    events = dict(store.rows("SELECT pid, event_date FROM meta", ()))
    recall_hits, leads, fp_rates = 0, [], []
    n_mas = n_norm = 0
    for pid, event_date in sorted(events.items()):
        seq = run_assessments(ts, pid)
        alert_days = [d for d, a in seq if a.level in ("yellow", "red")]
        if event_date:
            n_mas += 1
            before = [d for d in alert_days if d < event_date]
            if before:
                recall_hits += 1
                first = dt.date.fromisoformat(min(before))
                leads.append(
                    (dt.date.fromisoformat(event_date) - first).days * 24)
        else:
            n_norm += 1
            fp_rates.append(_episodes(alert_days) / (DAYS / 30))
    return {
        "recall": recall_hits / n_mas if n_mas else 0.0,
        "lead_hours_min": min(leads) if leads else 0,
        "fp_episodes_per_pm": round(sum(fp_rates) / n_norm, 3) if n_norm else 0.0,
    }


if __name__ == "__main__":
    import sys
    from rareguard.data.store import Store
    from synth.generate_dataset import generate
    store = Store(sys.argv[1] if len(sys.argv) > 1 else ":memory:")
    generate(store, seed=42)
    print(gate_metrics(store))
    store.close()
