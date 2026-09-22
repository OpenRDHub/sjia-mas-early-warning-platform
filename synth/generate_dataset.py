"""合成 SJA 患儿时序数据（同时充当评测集）。取值依据见 docs/references.md。
运行 `python -m synth.generate_dataset` 重新生成（seed=42 完全可复现）。"""
import datetime as dt
import random

START = dt.date(2026, 1, 1)
DAYS = 180
PRODROME = 10          # MAS 前驱期天数
CODES = ["ferritin", "plt", "fib", "crp", "esr", "alt", "tg"]
BASE = {"ferritin": 110, "plt": 320, "fib": 3.2, "crp": 12,
        "esr": 28, "alt": 25, "tg": 1.2}
NOISE = {"ferritin": .25, "plt": .12, "fib": .10, "crp": .20,
         "esr": .15, "alt": .20, "tg": .15}
# 正常轨迹钳制范围，确保不触发任何规则（评测公平性前提）
CLAMP = {"ferritin": (None, 300), "plt": (200, None), "fib": (2.2, None),
         "crp": (None, 20), "esr": (None, 60), "alt": (None, 60),
         "tg": (None, 2.5)}
MAS_TRAJ = {
    "ferritin": [320, 400, 520, 700, 950, 1300],
    "plt": [300, 270, 240, 200, 160, 120],
    "fib": [3.4, 3.1, 2.7, 2.2, 1.7, 1.3],
    "crp": [14, 18, 24, 33, 45, 60],
    "esr": [30, 26, 20, 14, 9, 6],
    "alt": [28, 35, 48, 66, 95, 130],
    "tg": [1.3, 1.6, 2.1, 2.7, 3.4, 4.2],
}
TEMP_TRAJ = [37.0, 38.6, 38.9, 39.4, 39.8, 40.1]
REF = {"ferritin": (7, 140), "plt": (150, 450), "fib": (2.0, 4.0),
       "crp": (0, 8), "esr": (0, 20), "alt": (0, 40), "tg": (0, 1.7)}
PATIENTS = {"P01": None, "P02": None, "P03": None, "P04": None,
            "P05": 89, "P06": 149}   # 值 = MAS 事件日索引


def generate(store, seed: int = 42) -> dict:
    kinds = {}
    store.conn.execute(
        "CREATE TABLE IF NOT EXISTS meta(pid TEXT PRIMARY KEY, event_date TEXT)")
    for pid, event in PATIENTS.items():
        rng = random.Random(f"{seed}-{pid}")
        store.add_patient(pid, f"患儿{pid}", "2014-01-01")
        cur = dict(BASE)
        for day in range(DAYS):
            date = (START + dt.timedelta(days=day)).isoformat()
            if event is not None and event - PRODROME <= day <= event:
                idx = int((day - (event - PRODROME)) / PRODROME * 5)
                for code in CODES:
                    lo, hi = REF[code]
                    store.add_lab(pid, date, code, MAS_TRAJ[code][idx], lo, hi)
                temp = TEMP_TRAJ[idx]
                sym = {"fever": 1, "rash": 7, "abdominal_pain": 5}
            else:
                if day % 2 == 0:
                    for code in CODES:
                        cur[code] *= 1 + rng.uniform(-NOISE[code], NOISE[code])
                        lo, hi = CLAMP[code]
                        cur[code] = min(max(cur[code], lo or 0), hi or 1e9)
                        rl, rh = REF[code]
                        store.add_lab(pid, date, code,
                                      round(cur[code], 2), rl, rh)
                temp = 36.8 + rng.uniform(-0.4, 0.4 if event is None else 0.6)
                sym = {}
            store.add_checkin(pid, date, round(temp, 1), sym)
        store.conn.execute(
            "INSERT OR REPLACE INTO meta VALUES(?,?)",
            (pid, (START + dt.timedelta(days=event)).isoformat()
             if event is not None else None))
        store.conn.commit()
        kinds[pid] = "mas" if event is not None else "normal"
    return kinds


if __name__ == "__main__":
    from rareguard.data.store import Store
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/rareguard.db")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    s = Store(args.out)
    print(generate(s, seed=args.seed))
    s.close()
