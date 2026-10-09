"""演示数据播种：写入近三日、可复现的 SJA→MAS 高危样例，供离线彩排与截图取证。

数据全部为合成值（非真实患儿）。日期相对系统当日计算，使前端默认 90 天趋势窗口
能画出上升曲线。用法：
    python scripts/seed_demo_db.py [db_path]
默认写入 data/demo/rareguard_demo.db，并打印 pid 与 as_of。
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rareguard.data.store import Store  # noqa: E402

PID = "PDEMO"
REFS = {  # code -> (ref_low, ref_high)
    "ferritin": (15, 150), "plt": (125, 350), "fib": (2, 4),
    "alt": (0, 40), "tg": (0, 1.7), "esr": (0, 15), "crp": (0, 5),
}
# (offset_days_ago, {code: value}, temp, symptoms) —— 绿→黄→红三级爬升
TRAJECTORY = [
    (2, {"ferritin": 450, "plt": 160, "fib": 2.6, "crp": 20},
     38.0, {"rash": 2}),
    (1, {"ferritin": 620, "plt": 140, "fib": 2.0, "crp": 28},
     38.8, {"rash": 4}),
    (0, {"ferritin": 1200, "plt": 80, "fib": 1.2, "alt": 110,
         "tg": 3.6, "crp": 60, "esr": 8},
     39.6, {"rash": 6}),
]


def seed(db_path: str) -> dict:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    store = Store(db_path)
    today = date.today()
    store.add_patient(PID, "演示患儿", "2016-05-01")
    for ago, labs, temp, symptoms in TRAJECTORY:
        day = (today - timedelta(days=ago)).isoformat()
        store.add_checkin(PID, day, temp, symptoms)
        for code, value in labs.items():
            lo, hi = REFS[code]
            store.add_lab(PID, day, code, value, lo, hi, source="demo")
    store.close()
    return {"db": db_path, "pid": PID, "as_of": today.isoformat()}


if __name__ == "__main__":
    import json

    path = sys.argv[1] if len(sys.argv) > 1 else "data/demo/rareguard_demo.db"
    print(json.dumps(seed(path), ensure_ascii=False))
