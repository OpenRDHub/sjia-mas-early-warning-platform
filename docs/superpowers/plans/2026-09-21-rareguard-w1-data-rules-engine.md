# RareGuard W1：数据层 + 规则趋势引擎 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 medassist P0a 骨架 fork 为 RareGuard 项目，交付确定性 MAS 预警引擎（数据层 + 归一化 + R-A/R-B/R-C 规则 + 合成数据集 + 评测门禁）。

**Architecture:** 风险结论 100% 出自纯规则引擎（不经 LLM），SQLite 时序存储经 TimeSeriesProvider 抽象只读访问；合成数据集同时充当评测集，门禁不达标 = 阻断。

**Tech Stack:** Python 3.11+、pytest 8、FastAPI（沿用基座，W1 不改动）、SQLite（WAL）。

**Spec:** `docs/superpowers/specs/2026-09-21-rareguard-t04-design.md`（本文档实现其 §2 分析引擎/数据层、§3.1 合成数据集、§5 门禁中 W1 可验证部分）

**里程碑定位:** W1（9.22–9.28）。W2（OCR/打卡/护栏家庭化）、W3（前端四屏/离线降级）、W4（彩排）各自单独立项出计划——本计划不含其任务。

## Global Constraints

- Python >= 3.11；测试命令统一 `python -m pytest`，默认排除 `real_api` 标记（基座 pyproject 已配置）。
- 规则引擎、数据层、评测代码**禁止 import 任何 LLM 模块**（`medassist.llm`/`rareguard.llm`）——LLM 不参与判断是产品红线。
- 包名从 `medassist` 重命名为 `rareguard`；`verification/`、`llm/`、`api/`、`orchestrator/` 原样保留待 W2/W3 改造。
- 日期一律 ISO 字符串 `YYYY-MM-DD`；指标代码用小写规范名：`ferritin, crp, esr, plt, fib, alt, tg, temp`。
- 风险等级取值 `"green" | "yellow" | "red"`，排序 green<yellow<red。
- 不复制基座 `.env`、`audit_log.jsonl`、`.git/`；真实样例目录 `data/real_samples/` 必须进 `.gitignore`。
- 每个任务结束时全部测试通过并单独 commit。

## 文件结构

```
D:\APPs\罕见无界医学赛\
├── LICENSE Apache-2.0（新）
├── README.md（新，W1 只放架构图与复现命令）
├── .gitignore（改：追加 data/real_samples/、.env、*.db）
├── pyproject.toml（改：name=rareguard）
├── rareguard/
│   ├── data/store.py          Store：SQLite 写入层（Task 2）
│   ├── ts/provider.py         TimeSeriesProvider ABC + SqliteTimeSeries（Task 3）
│   ├── analysis/normalize.py  别名映射 + 单位归一（Task 4）
│   ├── analysis/rules.py      RuleHit + R-A 绝对阈值（Task 5）
│   ├── analysis/trends.py     R-B 趋势规则（Task 6）
│   ├── analysis/mas.py        R-C MAS 评分 + assess_patient 汇总（Task 7）
│   ├── verification/…         基座六层管道（保留，W2 改造）
│   ├── llm/ api/ orchestrator/ ehr/  基座模块（保留）
├── synth/generate_dataset.py  合成数据集（Task 8）
├── docs/references.md         规则取值文献登记（Task 8）
├── evals/gate_rareguard.py    门禁指标计算函数（Task 9）
└── tests/  test_store.py test_ts_provider.py test_normalize.py
           test_rules_absolute.py test_trends.py test_mas.py
           test_synth_dataset.py test_gate_rareguard.py
```

---

### Task 1: W0 脚手架 —— fork 基座、重命名、保持测试绿

**Files:**
- Create: `LICENSE`, `README.md`
- Modify: `.gitignore`, `pyproject.toml`
- Copy: `D:\APPs\辅助医疗\{medassist→rareguard, tests, evals}`（排除 `.env`、`audit_log.jsonl`、`.git`、`__pycache__`、`.pytest_cache`、`docs/screenshots`）

**Interfaces:**
- Produces: 可 import 的 `rareguard` 包（含基座全部模块），pytest 全绿基线。

- [ ] **Step 1: 复制基座代码**

```bash
cp -r "/d/APPs/辅助医疗/medassist" rareguard
cp -r "/d/APPs/辅助医疗/tests" tests
cp -r "/d/APPs/辅助医疗/evals" evals
cp "/d/APPs/辅助医疗/pyproject.toml" "/d/APPs/辅助医疗/requirements.txt" .
find rareguard tests evals -name __pycache__ -type d -exec rm -rf {} +
```

- [ ] **Step 2: 包名替换**

```bash
grep -rl "medassist" rareguard tests evals pyproject.toml | xargs sed -i 's/medassist/rareguard/g'
sed -i 's/^name = "rareguard"$/name = "rareguard"/' pyproject.toml  # 确认 name 行
```

- [ ] **Step 3: 补 .gitignore / LICENSE / README**

`.gitignore` 追加：

```
.env
*.db
data/real_samples/
__pycache__/
.pytest_cache/
```

`LICENSE`：Apache-2.0 全文（`https://www.apache.org/licenses/LICENSE-2.0.txt` 原文粘贴）。
`README.md` 初稿：项目一句话定位 + 架构图（从 spec §2 复制）+ `python -m pytest` 复现命令。

- [ ] **Step 4: 运行全量测试确认基线绿**

Run: `python -m pytest -q`
Expected: 全部通过（基座约 100+ 项；`real_api` 自动跳过）

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "chore: fork medassist 基座为 rareguard（不含 .env/审计日志），测试基线绿"
```

---

### Task 2: Store —— SQLite 时序写入层

**Files:**
- Create: `rareguard/data/store.py`, `rareguard/data/__init__.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: 无
- Produces: `Store(path: str)`，方法：
  - `add_patient(pid: str, name: str, dob: str) -> None`
  - `add_lab(pid: str, date: str, code: str, value: float, ref_low: float | None, ref_high: float | None, source: str = "synth") -> None`（同 pid+date+code 重复写入 = 覆盖）
  - `add_checkin(pid: str, date: str, temp: float | None, symptoms: dict[str, int]) -> None`（symptoms 序列化为 JSON）
  - `rows(sql: str, params: tuple) -> list[tuple]`（供 Task 3 只读查询用的通用出口）
  - `close() -> None`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_store.py
import json
import pytest
from rareguard.data.store import Store

@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "t.db")); yield s; s.close()

def test_add_and_query_lab(store):
    store.add_patient("P01", "小明", "2015-06-01")
    store.add_lab("P01", "2026-01-08", "ferritin", 620.0, 23.9, 336.2)
    rows = store.rows(
        "SELECT date, code, value FROM lab WHERE pid=? ORDER BY date", ("P01",))
    assert rows == [("2026-01-08", "ferritin", 620.0)]

def test_add_lab_upserts(store):
    store.add_patient("P01", "小明", "2015-06-01")
    store.add_lab("P01", "2026-01-08", "crp", 30.0, 0, 5)
    store.add_lab("P01", "2026-01-08", "crp", 33.0, 0, 5)
    assert store.rows("SELECT value FROM lab", ())[0][0] == 33.0

def test_add_checkin_serializes_symptoms(store):
    store.add_patient("P01", "小明", "2015-06-01")
    store.add_checkin("P01", "2026-01-08", 38.7, {"fever": 1, "rash": 6})
    raw = store.rows("SELECT temp, symptoms FROM checkin", ())[0]
    assert raw[0] == 38.7 and json.loads(raw[1]) == {"fever": 1, "rash": 6}
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_store.py -q` → Expected: FAIL（ModuleNotFoundError: rareguard.data.store）

- [ ] **Step 3: 最小实现**

```python
# rareguard/data/store.py
import json
import sqlite3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS patient(pid TEXT PRIMARY KEY, name TEXT, dob TEXT);
CREATE TABLE IF NOT EXISTS lab(
  pid TEXT, date TEXT, code TEXT, value REAL,
  ref_low REAL, ref_high REAL, source TEXT,
  PRIMARY KEY(pid, date, code));
CREATE TABLE IF NOT EXISTS checkin(
  pid TEXT, date TEXT, temp REAL, symptoms TEXT,
  PRIMARY KEY(pid, date));
"""

class Store:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(_SCHEMA)

    def add_patient(self, pid, name, dob):
        self.conn.execute(
            "INSERT OR REPLACE INTO patient VALUES(?,?,?)", (pid, name, dob))
        self.conn.commit()

    def add_lab(self, pid, date, code, value, ref_low, ref_high, source="synth"):
        self.conn.execute(
            "INSERT OR REPLACE INTO lab VALUES(?,?,?,?,?,?,?)",
            (pid, date, code, value, ref_low, ref_high, source))
        self.conn.commit()

    def add_checkin(self, pid, date, temp, symptoms):
        self.conn.execute(
            "INSERT OR REPLACE INTO checkin VALUES(?,?,?,?)",
            (pid, date, temp, json.dumps(symptoms, ensure_ascii=False)))
        self.conn.commit()

    def rows(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()

    def close(self):
        self.conn.close()
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_store.py -q` → Expected: 3 PASS

- [ ] **Step 5: Commit** `git commit -am "feat: SQLite 时序存储层 Store（patient/lab/checkin，upsert 语义）"`

---

### Task 3: TimeSeriesProvider —— 只读时序抽象

**Files:**
- Create: `rareguard/ts/provider.py`, `rareguard/ts/__init__.py`
- Test: `tests/test_ts_provider.py`

**Interfaces:**
- Consumes: `Store.rows`（Task 2）
- Produces（后续规则与评测全部依赖此契约）:

```python
@dataclass(frozen=True)
class LabPoint: date: str; code: str; value: float
                ref_low: float | None; ref_high: float | None
@dataclass(frozen=True)
class Checkin: date: str; temp: float | None; symptoms: dict[str, int]

class TimeSeriesProvider(ABC):   # 只读，无写方法（继承基座 R5 思想）
    def get_lab_series(pid, code, until: str | None = None) -> list[LabPoint]  # 按日期升序，until 含当日
    def get_checkins(pid, until: str | None = None) -> list[Checkin]
    def codes(self, pid) -> list[str]

class SqliteTimeSeries(TimeSeriesProvider):
    def __init__(self, store: Store): ...
```

- [ ] **Step 1: 写失败测试**

```python
# tests/test_ts_provider.py
from rareguard.data.store import Store
from rareguard.ts.provider import SqliteTimeSeries, LabPoint, Checkin

def make(store):
    store.add_patient("P01", "小明", "2015-06-01")
    store.add_lab("P01", "2026-01-08", "crp", 30.0, 0, 5)
    store.add_lab("P01", "2026-01-01", "crp", 12.0, 0, 5)
    store.add_lab("P01", "2026-01-15", "crp", 45.0, 0, 5)
    store.add_checkin("P01", "2026-01-08", 38.7, {"fever": 1})

def test_series_sorted_and_filtered(tmp_path):
    s = Store(str(tmp_path / "t.db")); make(s)
    ts = SqliteTimeSeries(s)
    pts = ts.get_lab_series("P01", "crp", until="2026-01-08")
    assert [p.date for p in pts] == ["2026-01-01", "2026-01-08"]
    assert pts[1] == LabPoint("2026-01-08", "crp", 30.0, 0, 5)

def test_checkins_deserialize(tmp_path):
    s = Store(str(tmp_path / "t.db")); make(s)
    ts = SqliteTimeSeries(s)
    assert ts.get_checkins("P01")[0] == Checkin("2026-01-08", 38.7, {"fever": 1})

def test_provider_has_no_write_methods():
    assert not [m for m in dir(TimeSeriesProvider) if m.startswith(("add_", "write_", "set_"))]
```

（末行需 `from rareguard.ts.provider import TimeSeriesProvider`。）

- [ ] **Step 2: 运行确认失败** → ModuleNotFoundError
- [ ] **Step 3: 实现**

```python
# rareguard/ts/provider.py
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass(frozen=True)
class LabPoint:
    date: str; code: str; value: float
    ref_low: "float | None"; ref_high: "float | None"

@dataclass(frozen=True)
class Checkin:
    date: str; temp: "float | None"; symptoms: dict

class TimeSeriesProvider(ABC):
    """Read-only by design: no write methods exist on this interface."""

    @abstractmethod
    def get_lab_series(self, pid, code, until=None) -> list[LabPoint]: ...
    @abstractmethod
    def get_checkins(self, pid, until=None) -> list[Checkin]: ...
    @abstractmethod
    def codes(self, pid) -> list[str]: ...

class SqliteTimeSeries(TimeSeriesProvider):
    def __init__(self, store):
        self._store = store

    def get_lab_series(self, pid, code, until=None):
        sql = "SELECT date, code, value, ref_low, ref_high FROM lab WHERE pid=? AND code=?"
        params: list = [pid, code]
        if until:
            sql += " AND date<=?"; params.append(until)
        sql += " ORDER BY date"
        return [LabPoint(*r) for r in self._store.rows(sql, tuple(params))]

    def get_checkins(self, pid, until=None):
        sql = "SELECT date, temp, symptoms FROM checkin WHERE pid=?"
        params: list = [pid]
        if until:
            sql += " AND date<=?"; params.append(until)
        sql += " ORDER BY date"
        return [Checkin(d, t, json.loads(s)) for d, t, s in self._store.rows(sql, tuple(params))]

    def codes(self, pid):
        return [r[0] for r in self._store.rows(
            "SELECT DISTINCT code FROM lab WHERE pid=? ORDER BY code", (pid,))]
```

- [ ] **Step 4: 通过** → 3 PASS
- [ ] **Step 5: Commit** `feat: TimeSeriesProvider 只读抽象 + SqliteTimeSeries`

---

### Task 4: 指标归一化（别名 + 单位换算）

**Files:**
- Create: `rareguard/analysis/normalize.py`, `rareguard/analysis/__init__.py`
- Test: `tests/test_normalize.py`

**Interfaces:**
- Produces: `normalize(code_or_alias: str, value: float, unit: str) -> tuple[str, float]`，返回 `(规范代码, 规范单位下的值)`；未知别名抛 `UnknownIndicator`，不可换算单位抛 `UnitConversionError`。
- 规范单位：ferritin=ng/mL, crp=mg/L, esr=mm/h, plt=10⁹/L, fib=g/L, alt=U/L, tg=mmol/L, temp=℃。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_normalize.py
import pytest
from rareguard.analysis.normalize import (
    normalize, UnknownIndicator, UnitConversionError)

def test_chinese_alias():
    assert normalize("血清铁蛋白", 620, "ng/mL") == ("ferritin", 620.0)
    assert normalize("C反应蛋白", 3.2, "mg/dL") == ("crp", 32.0)

def test_unit_equivalence():
    assert normalize("铁蛋白", 620, "μg/L") == ("ferritin", 620.0)  # μg/L ≡ ng/mL

def test_fib_mgdl_to_gl():
    assert normalize("纤维蛋白原", 1200, "mg/L") == ("fib", 1.2)

def test_tg_mgdl_to_mmol():
    code, v = normalize("甘油三酯", 266, "mg/dL")
    assert code == "tg" and abs(v - 3.0) < 0.01

def test_temp_f_to_c():
    assert normalize("体温", 101.3, "°F") == ("temp", 38.5)

def test_errors():
    with pytest.raises(UnknownIndicator): normalize("血糖", 5, "mmol/L")
    with pytest.raises(UnitConversionError): normalize("铁蛋白", 5, "g/dL")
```

- [ ] **Step 2: 失败** → [ ] **Step 3: 实现**

```python
# rareguard/analysis/normalize.py
class UnknownIndicator(Exception): pass
class UnitConversionError(Exception): pass

ALIASES = {
    "血清铁蛋白": "ferritin", "铁蛋白": "ferritin", "ferritin": "ferritin",
    "c反应蛋白": "crp", "crp": "crp",
    "血沉": "esr", "红细胞沉降率": "esr", "esr": "esr",
    "血小板": "plt", "血小板计数": "plt", "plt": "plt",
    "纤维蛋白原": "fib", "fib": "fib",
    "谷丙转氨酶": "alt", "丙氨酸氨基转移酶": "alt", "alt": "alt",
    "甘油三酯": "tg", "tg": "tg",
    "体温": "temp", "temp": "temp",
}
# 规范单位换算表：code -> {输入单位: (乘系数, 加偏移)}
UNITS: dict[str, dict[str, tuple[float, float]]] = {
    "ferritin": {"ng/ml": (1, 0), "μg/l": (1, 0), "ug/l": (1, 0), "ng/ml*1": (1, 0)},
    "crp": {"mg/l": (1, 0), "mg/dl": (10, 0)},
    "esr": {"mm/h": (1, 0)},
    "plt": {"10^9/l": (1, 0), "g/l": (1, 0), "×10⁹/l": (1, 0)},
    "fib": {"g/l": (1, 0), "mg/l": (0.001, 0), "mg/dl": (0.01, 0)},
    "alt": {"u/l": (1, 0), "iu/l": (1, 0)},
    "tg": {"mmol/l": (1, 0), "mg/dl": (1 / 88.57, 0)},
    "temp": {"℃": (1, 0), "c": (1, 0), "°f": (1 / 1.8, -32 / 1.8)},
}

def normalize(code_or_alias: str, value: float, unit: str) -> tuple[str, float]:
    code = ALIASES.get(code_or_alias.strip().lower()) or ALIASES.get(code_or_alias.strip())
    if code is None:
        raise UnknownIndicator(code_or_alias)
    key = unit.strip().lower()
    table = UNITS[code]
    if key not in table:
        raise UnitConversionError(f"{code}: {unit}")
    factor, offset = table[key]
    return code, value * factor + offset
```

（注意 `ALIASES` 键大小写：中文键查 `strip()` 原值，英文键查 `lower()`；实现里两次 `.get` 已覆盖。`"ng/ml*1"` 是化验单常见写法，保留。）

- [ ] **Step 4: 通过** → [ ] **Step 5: Commit** `feat: 指标别名与单位归一化（OCR 入库前置契约）`

---

### Task 5: R-A 绝对阈值规则

**Files:**
- Create: `rareguard/analysis/rules.py`
- Test: `tests/test_rules_absolute.py`

**Interfaces:**
- Consumes: `LabPoint`、`Checkin`（Task 3）
- Produces:

```python
@dataclass(frozen=True)
class RuleHit:
    rule_id: str; name: str; level: str  # yellow|red
    evidence: dict                        # 人类可读证据（值、单位、日期）

def eval_absolute(series: dict[str, list[LabPoint]],
                  checkins: list[Checkin]) -> list[RuleHit]
```
`series` 键为规范代码，值为升序 LabPoint 列表；规则只看 `until` 截断后的数据（截断由调用方完成）。

- 阈值表（红优先于黄，取最高档）：

| id | 指标 | yellow | red |
|---|---|---|---|
| A1 | ferritin | ≥500 | ≥1000 |
| A2 | plt | <100 | <50 |
| A3 | fib | <1.5 | <1.0 |
| A4 | alt | >80 | >160 |
| A5 | tg | >3.0 | >4.0 |
| A6 | temp（最新打卡） | ≥38.5 | ≥39.0 |
| A7 | esr≤10 且 crp≥30（沉-CRP 分离） | — | 命中即 red |

- [ ] **Step 1: 写失败测试**

```python
# tests/test_rules_absolute.py
from rareguard.ts.provider import LabPoint, Checkin
from rareguard.analysis.rules import eval_absolute

def lp(code, date, v): return LabPoint(date, code, v, None, None)

def test_ferritin_yellow_and_red():
    s = {"ferritin": [lp("ferritin", "2026-01-08", 620)]}
    hits = eval_absolute(s, [])
    assert [h.level for h in hits if h.rule_id == "A1"] == ["yellow"]
    s = {"ferritin": [lp("ferritin", "2026-01-08", 1200)]}
    assert eval_absolute(s, [])[0].level == "red"

def test_esr_crp_dissociation_red():
    s = {"esr": [lp("esr", "2026-01-08", 8)], "crp": [lp("crp", "2026-01-08", 45)]}
    hits = eval_absolute(s, [])
    assert any(h.rule_id == "A7" and h.level == "red" for h in hits)

def test_fever_from_checkin():
    hits = eval_absolute({}, [Checkin("2026-01-08", 39.2, {})])
    assert hits and hits[0].rule_id == "A6" and hits[0].level == "red"

def test_normal_patient_no_hits():
    s = {"ferritin": [lp("ferritin", "2026-01-08", 120)],
         "plt": [lp("plt", "2026-01-08", 350)],
         "crp": [lp("crp", "2026-01-08", 8)]}
    assert eval_absolute(s, [Checkin("2026-01-08", 36.8, {})]) == []

def test_hit_carries_evidence():
    h = eval_absolute({"ferritin": [lp("ferritin", "2026-01-08", 1200)]}, [])[0]
    assert h.evidence["value"] == 1200 and h.evidence["date"] == "2026-01-08"
```

- [ ] **Step 2: 失败** → [ ] **Step 3: 实现**

```python
# rareguard/analysis/rules.py
from dataclasses import dataclass

@dataclass(frozen=True)
class RuleHit:
    rule_id: str
    name: str
    level: str
    evidence: dict

def _latest(points):
    return points[-1] if points else None

# 每项: (id, code, 判定函数(value)->level|None, 名称)
_THRESHOLDS = [
    ("A1", "ferritin", lambda v: "red" if v >= 1000 else "yellow" if v >= 500 else None, "铁蛋白升高"),
    ("A2", "plt",      lambda v: "red" if v < 50 else "yellow" if v < 100 else None, "血小板减少"),
    ("A3", "fib",      lambda v: "red" if v < 1.0 else "yellow" if v < 1.5 else None, "纤维蛋白原降低"),
    ("A4", "alt",      lambda v: "red" if v > 160 else "yellow" if v > 80 else None, "转氨酶升高"),
    ("A5", "tg",       lambda v: "red" if v > 4.0 else "yellow" if v > 3.0 else None, "甘油三酯升高"),
]

def eval_absolute(series: dict, checkins: list) -> list:
    hits: list[RuleHit] = []
    for rule_id, code, check, name in _THRESHOLDS:
        p = _latest(series.get(code, []))
        if p and (lv := check(p.value)):
            hits.append(RuleHit(rule_id, name, lv,
                                {"value": p.value, "date": p.date, "code": code}))
    # A6 体温（取最新打卡）
    if checkins and (c := checkins[-1]).temp is not None:
        lv = "red" if c.temp >= 39.0 else "yellow" if c.temp >= 38.5 else None
        if lv:
            hits.append(RuleHit("A6", "发热", lv,
                                {"value": c.temp, "date": c.date, "code": "temp"}))
    # A7 血沉-CRP 分离
    esr, crp = _latest(series.get("esr", [])), _latest(series.get("crp", []))
    if esr and crp and esr.value <= 10 and crp.value >= 30:
        hits.append(RuleHit("A7", "血沉-CRP分离", "red",
                            {"esr": esr.value, "crp": crp.value, "date": crp.date}))
    return hits
```

- [ ] **Step 4: 通过** → [ ] **Step 5: Commit** `feat: R-A 绝对阈值规则（7 条，含血沉-CRP 分离）`

---

### Task 6: R-B 趋势规则（抗噪声）

**Files:**
- Create: `rareguard/analysis/trends.py`
- Test: `tests/test_trends.py`

**Interfaces:**
- Consumes: `LabPoint`、`RuleHit`（Task 5）
- Produces: `eval_trend(series: dict[str, list[LabPoint]]) -> list[RuleHit]`
- **抗噪声设计**：连续上升须每步 ≥+15% 且末值超最小绝对值，否则基线噪声会误触发——这是误报率门禁的关键。

| id | 条件 | level |
|---|---|---|
| B1 | crp 连续≥3 点每步 ≥+15% 且末值 ≥30 | yellow |
| B2 | ferritin 连续≥3 点每步 ≥+15% 且末值 ≥400 | yellow |
| B3 | plt 连续≥3 点每步 ≥-8% 且末值 <150 | yellow |
| B4 | plt 连降≥2（每步≥-8%）且 fib 连降≥2（每步≥-10%）同窗 | red |
| B5 | ferritin 14 天内涨幅 ≥100%（首末两点） | red |

- [ ] **Step 1: 写失败测试**

```python
# tests/test_trends.py
from rareguard.ts.provider import LabPoint
from rareguard.analysis.trends import eval_trend

def lp(code, date, v): return LabPoint(date, code, v, None, None)
def series(code, vals):
    return {code: [lp(code, f"2026-01-{i+1:02d}", v) for i, v in enumerate(vals)]}

def test_crp_rising_triggers_b1():
    hits = eval_trend(series("crp", [12, 18, 32]))
    assert [h.rule_id for h in hits] == ["B1"] and hits[0].level == "yellow"

def test_noise_does_not_trigger():
    assert eval_trend(series("crp", [12.0, 12.4, 12.1])) == []
    assert eval_trend(series("crp", [8, 10, 11.4])) == []   # 末值未到 30

def test_ferritin_doubling_is_red_b5():
    s = {"ferritin": [lp("ferritin", "2026-01-01", 300),
                      lp("ferritin", "2026-01-12", 660)]}
    ids = {h.rule_id for h in eval_trend(s)}
    assert "B5" in ids

def test_plt_fib_cooldown_is_red_b4():
    s = {"plt": [lp("plt", f"2026-01-{i+1:02d}", v) for i, v in enumerate([220, 190, 160])],
         "fib": [lp("fib", f"2026-01-{i+1:02d}", v) for i, v in enumerate([3.2, 2.6, 2.0])]}
    hits = eval_trend(s)
    assert any(h.rule_id == "B4" and h.level == "red" for h in hits)
```

- [ ] **Step 2: 失败** → [ ] **Step 3: 实现**

```python
# rareguard/analysis/trends.py
from rareguard.analysis.rules import RuleHit

def _ratios(vals):
    return [b / a for a, b in zip(vals, vals[1:])]

def _rising(vals, step_min, last_min) -> bool:
    if len(vals) < 3 or vals[-1] < last_min:
        return False
    return all(r >= 1 + step_min for r in _ratios(vals[-3:]))

def _falling_tail(vals, step_max, n):
    if len(vals) < n + 1:
        return False
    return all(r <= 1 - step_max for r in _ratios(vals[-(n + 1):]))

def eval_trend(series: dict) -> list:
    hits: list[RuleHit] = []
    def vals(code):
        return [p.value for p in series.get(code, [])]
    v = vals("crp")
    if _rising(v, 0.15, 30):
        hits.append(RuleHit("B1", "CRP连续上升", "yellow", {"last": v[-1]}))
    f = vals("ferritin")
    if _rising(f, 0.15, 400):
        hits.append(RuleHit("B2", "铁蛋白连续上升", "yellow", {"last": f[-1]}))
    if len(f) >= 2 and f[0] > 0 and f[-1] / f[0] >= 2 and (
            series["ferritin"][-1].date, series["ferritin"][0].date) and \
            _days_between(series["ferritin"][0].date, series["ferritin"][-1].date) <= 14:
        hits.append(RuleHit("B5", "铁蛋白14天内翻倍", "red", {"from": f[0], "to": f[-1]}))
    p = vals("plt")
    if len(p) >= 3 and p[-1] < 150 and all(r <= 0.92 for r in _ratios(p[-3:])):
        hits.append(RuleHit("B3", "血小板连续下降", "yellow", {"last": p[-1]}))
    fb = vals("fib")
    if _falling_tail(p, 0.08, 2) and _falling_tail(fb, 0.10, 2):
        hits.append(RuleHit("B4", "血小板+纤维蛋白原同向下降", "red",
                            {"plt": p[-1], "fib": fb[-1]}))
    return hits

def _days_between(d1: str, d2: str) -> int:
    from datetime import date
    a = date.fromisoformat(d1); b = date.fromisoformat(d2)
    return (b - a).days
```

（实现注意：B5 判定简化为 `f[-1]/f[0]>=2 且首末日期差 ≤14 天`；上面条件表达式中冗余的 tuple 判断请实现时删除，只保留 `_days_between(...) <= 14` 与涨幅判断。）

- [ ] **Step 4: 通过**（若 B5 测试因表达式冗余失败，按上述注释修正后重跑）
- [ ] **Step 5: Commit** `feat: R-B 趋势规则（每步最小增幅抗噪声设计）`

---

### Task 7: R-C MAS 评分 + assess_patient 汇总

**Files:**
- Create: `rareguard/analysis/mas.py`
- Test: `tests/test_mas.py`

**Interfaces:**
- Consumes: Task 3/5/6 全部
- Produces:

```python
@dataclass(frozen=True)
class Assessment:
    level: str            # green|yellow|red
    score: float          # 0-100
    hits: tuple[RuleHit, ...]

def mas_score(series, checkins) -> tuple[float, dict]     # (score, 分项明细)
def assess_patient(ts: TimeSeriesProvider, pid: str, as_of: str) -> Assessment
```
- 评分 8 项 × 12.5 分：发热（近 7 天 ≥3 次 temp≥38.5 得满分，≥1 次得 6.25）、ferritin≥500、plt<100、fib<1.5、alt>80、tg>3、沉-CRP 分离、症状项（rash 或 abdominal_pain VAS≥5 的最新打卡）。
- 定级：`score≥70 或 red 命中≥2 → red`；`score≥40 或 任一命中 → yellow`；否则 green。
- `assess_patient` 内部用 `until=as_of` 截断（含当日），**不 import LLM**。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_mas.py
from rareguard.data.store import Store
from rareguard.ts.provider import SqliteTimeSeries
from rareguard.analysis.mas import assess_patient, mas_score

def seed_mas_patient(s):
    s.add_patient("P05", "小红", "2013-03-02")
    # 发作前 10 天：铁蛋白爬升翻倍、plt/fib 下坠、CRP 升、持续高热
    for i, (fer, pl, fb, crp, t) in enumerate([
        (320, 300, 3.4, 14, 37.0), (400, 270, 3.1, 18, 38.6),
        (520, 240, 2.7, 24, 38.9), (700, 200, 2.2, 33, 39.4),
        (950, 160, 1.7, 45, 39.8),
    ]):
        d = f"2026-02-{10+i*2:02d}"
        for code, v, rl, rh in [("ferritin", fer, 7, 140), ("plt", pl, 150, 450),
                                 ("fib", fb, 2, 4), ("crp", crp, 0, 8)]:
            s.add_lab("P05", d, code, v, rl, rh)
        s.add_checkin("P05", d, t, {"fever": 1, "rash": 7})

def test_assess_patient_red(tmp_path):
    s = Store(str(tmp_path / "t.db")); seed_mas_patient(s)
    a = assess_patient(SqliteTimeSeries(s), "P05", "2026-02-18")
    assert a.level == "red" and a.score >= 70

def test_green_patient(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.add_patient("P01", "小明", "2015-06-01")
    s.add_lab("P01", "2026-02-10", "ferritin", 120, 7, 140)
    s.add_checkin("P01", "2026-02-10", 36.7, {})
    a = assess_patient(SqliteTimeSeries(s), "P01", "2026-02-18")
    assert a.level == "green" and a.score == 0

def test_until_truncation(tmp_path):
    s = Store(str(tmp_path / "t.db")); seed_mas_patient(s)
    early = assess_patient(SqliteTimeSeries(s), "P05", "2026-02-10")
    late = assess_patient(SqliteTimeSeries(s), "P05", "2026-02-18")
    assert early.score < late.score

def test_no_llm_import():
    import subprocess, sys
    r = subprocess.run([sys.executable, "-c",
        "import rareguard.analysis.mas as m;"
        "import sys; assert not [x for x in sys.modules if 'rareguard.llm' in x]"],
        capture_output=True)
    assert r.returncode == 0
```

- [ ] **Step 2: 失败** → [ ] **Step 3: 实现**

```python
# rareguard/analysis/mas.py
from dataclasses import dataclass
from rareguard.analysis.rules import RuleHit, eval_absolute
from rareguard.analysis.trends import eval_trend

@dataclass(frozen=True)
class Assessment:
    level: str
    score: float
    hits: tuple

def _last(series, code):
    pts = series.get(code, [])
    return pts[-1].value if pts else None

def mas_score(series: dict, checkins: list) -> tuple:
    detail = {}
    fever_days = sum(1 for c in checkins[-7:] if (c.temp or 0) >= 38.5)
    detail["fever"] = 12.5 if fever_days >= 3 else 6.25 if fever_days >= 1 else 0.0
    def band(code, thr, invert=False):
        v = _last(series, code)
        if v is None: return 0.0
        return 12.5 if (v < thr if invert else v > thr) else 0.0
    detail["ferritin"] = band("ferritin", 500)
    detail["plt"] = band("plt", 100, invert=True)
    detail["fib"] = band("fib", 1.5, invert=True)
    detail["alt"] = band("alt", 80)
    detail["tg"] = band("tg", 3.0)
    esr, crp = _last(series, "esr"), _last(series, "crp")
    detail["esr_crp_sep"] = 12.5 if (esr is not None and crp is not None
                                     and esr <= 10 and crp >= 30) else 0.0
    sym = checkins[-1].symptoms if checkins else {}
    detail["symptoms"] = 12.5 if max(sym.get("rash", 0),
                                     sym.get("abdominal_pain", 0)) >= 5 else 0.0
    return round(sum(detail.values()), 2), detail

def assess_patient(ts, pid: str, as_of: str) -> Assessment:
    codes = ts.codes(pid)
    series = {c: ts.get_lab_series(pid, c, until=as_of) for c in codes}
    checkins = ts.get_checkins(pid, until=as_of)
    hits = tuple(eval_absolute(series, checkins) + eval_trend(series))
    score, _ = mas_score(series, checkins)
    reds = sum(1 for h in hits if h.level == "red")
    level = ("red" if score >= 70 or reds >= 2
             else "yellow" if score >= 40 or hits else "green")
    return Assessment(level=level, score=score, hits=hits)
```

- [ ] **Step 4: 通过** → [ ] **Step 5: Commit** `feat: R-C MAS 八项评分与 assess_patient 分级汇总`

---

### Task 8: 合成数据集 + 文献登记

**Files:**
- Create: `synth/generate_dataset.py`, `synth/__init__.py`, `docs/references.md`
- Test: `tests/test_synth_dataset.py`

**Interfaces:**
- Consumes: Store（Task 2）
- Produces: `generate(store: Store, seed: int = 42) -> dict[str, str]`，返回 `{pid: "normal"|"mas"}`；MAS 病例事件日写入表 `meta(pid, event_date)`。基线参数（写入实现，取值依据登记于 references.md）：

| code | 基线均值 | 波动 | MAS 前 10 天轨迹（5 个双日采样点） |
|---|---|---|---|
| ferritin | 110 | ±25% 随机游走 | 320→400→520→700→950→1300 |
| plt | 320 | ±12% | 300→270→240→200→160→120 |
| fib | 3.2 | ±10% | 3.4→3.1→2.7→2.2→1.7→1.3 |
| crp | 12 | ±20% | 14→18→24→33→45→60 |
| esr | 28 | ±15% | 30→26→20→14→9→6（分离现象） |
| alt | 25 | ±20% | 28→35→48→66→95→130 |
| tg | 1.2 | ±15% | 1.3→1.6→2.1→2.7→3.4→4.2 |
| temp(打卡) | 36.8 | ±0.4 | 37.0→38.6→38.9→39.4→39.8→40.1 |

- 采样节奏：化验每 2 天一次（MAS 病例发作前 10 天用轨迹表逐点，其余用基线×随机游走，游走步长受 `random.Random(seed+pid)` 控制）；打卡每天一次。P01–P04 正常 180 天；P05 事件日 = 起始日+89（即第 90 天），P06 = 第 150 天；事件日前 10 天为前驱期（用上表）。
- 正常病例随机游走必须**不触发**任何规则：实现时将正常轨迹钳制在 `ferritin<300, plt>200, fib>2.2, crp<20, temp<38.0` 范围内（`min/max` 截断），并在测试中断言正常病例全程 assess 无 red。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_synth_dataset.py
from rareguard.data.store import Store
from rareguard.ts.provider import SqliteTimeSeries
from rareguard.analysis.mas import assess_patient
from synth.generate_dataset import generate

def test_generate_shape(tmp_path):
    s = Store(str(tmp_path / "d.db"))
    kinds = generate(s, seed=42)
    assert sorted(kinds) == [f"P0{i}" for i in range(1, 7)]
    assert list(kinds.values()).count("mas") == 2
    labs = s.rows("SELECT COUNT(*) FROM lab", ())[0][0]
    assert labs > 6 * 90 * 6   # 每人 180 天双日采样 × 多指标
    s.close()

def test_deterministic(tmp_path):
    a = Store(str(tmp_path / "a.db")); b = Store(str(tmp_path / "b.db"))
    generate(a, seed=42); generate(b, seed=42)
    ra = a.rows("SELECT pid,date,code,value FROM lab ORDER BY pid,date,code", ())
    rb = b.rows("SELECT pid,date,code,value FROM lab ORDER BY pid,date,code", ())
    assert ra == rb
    a.close(); b.close()

def test_normal_patients_never_red(tmp_path):
    s = Store(str(tmp_path / "d.db")); generate(s, seed=42)
    ts = SqliteTimeSeries(s)
    for pid in ["P01", "P02", "P03", "P04"]:
        for day in range(0, 180, 10):
            d = f"2026-{1 + (day)//31:02d}-{(day)%28 + 1:02d}"
            assert assess_patient(ts, pid, d).level != "red", (pid, d)
    s.close()
```

- [ ] **Step 2: 失败** → [ ] **Step 3: 实现** `synth/generate_dataset.py`：

```python
"""合成 SJA 患儿时序数据（充当评测集）。取值依据见 docs/references.md。"""
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
CLAMP = {"ferritin": (None, 300), "plt": (200, None), "fib": (2.2, None),
         "crp": (None, 20), "esr": (None, 60), "alt": (None, 60), "tg": (None, 2.5)}
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
                        store.add_lab(pid, date, code, round(cur[code], 2), rl, rh)
                temp = 36.8 + rng.uniform(-0.4, 0.4 if event is None else 0.6)
                sym = {}
            store.add_checkin(pid, date, round(temp, 1), sym)
        store.conn.execute(
            "CREATE TABLE IF NOT EXISTS meta(pid TEXT PRIMARY KEY, event_date TEXT)")
        store.conn.execute("INSERT OR REPLACE INTO meta VALUES(?,?)",
                           (pid, (START + dt.timedelta(days=event)).isoformat()
                            if event is not None else None))
        store.conn.commit()
        kinds[pid] = "mas" if event is not None else "normal"
    return kinds
```

（若 `Store` 无 `conn` 暴露，可在 Store 增一个 `execute(sql, params)` 通用方法并同步改 Task 2 测试——优先选前者，改动最小。）

`docs/references.md`：逐条登记——HLH-2004 标准（Ferrari 2021, Blood Rev）、sJIA-MAS 2016 分类标准（Ravelli 2016, ACR）、铁蛋白阈值文献、血沉-CRP 分离现象文献；每条含"本系统取值 + 出处页码/表号"。

- [ ] **Step 4: 通过** → [ ] **Step 5: Commit** `feat: 合成数据集生成器（6 患儿×180 天，2 例 MAS）+ 文献登记`

---

### Task 9: 评测门禁（召回 100% / 提前 ≥48h / 误报 ≤1·患者·月）

**Files:**
- Create: `evals/gate_rareguard.py`
- Test: `tests/test_gate_rareguard.py`

**Interfaces:**
- Consumes: Task 3/7/8
- Produces:
  - `run_assessments(ts, pid) -> list[tuple[str, Assessment]]`（逐日）
  - `gate_metrics(store) -> dict`：`{"recall": 1.0, "lead_hours_min": int, "fp_episodes_per_pm": float}`
  - pytest 门禁用例，不达标即红。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_gate_rareguard.py
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
```

- [ ] **Step 2: 失败** → [ ] **Step 3: 实现**

```python
# evals/gate_rareguard.py
import datetime as dt
from rareguard.ts.provider import SqliteTimeSeries
from rareguard.analysis.mas import assess_patient

START = dt.date(2026, 1, 1)
DAYS = 180

def run_assessments(ts, pid):
    out = []
    for day in range(DAYS):
        d = (START + dt.timedelta(days=day)).isoformat()
        out.append((d, assess_patient(ts, pid, d)))
    return out

def _episodes(alert_days: list[str]) -> int:
    """连续预警日计为 1 次 episode。"""
    return sum(1 for i, d in enumerate(alert_days)
               if i == 0 or (dt.date.fromisoformat(d)
                             - dt.date.fromisoformat(alert_days[i - 1])).days > 1)

def gate_metrics(store):
    ts = SqliteTimeSeries(store)
    events = dict(store.rows("SELECT pid, event_date FROM meta", ()))
    recall_hits, leads, fp = 0, [], 0
    for pid, event_date in events.items():
        seq = run_assessments(ts, pid)
        alert_days = [d for d, a in seq if a.level in ("yellow", "red")]
        if event_date:
            alarmed_before = [d for d in alert_days if d < event_date]
            if alarmed_before:
                recall_hits += 1
                first = dt.date.fromisoformat(min(alarmed_before))
                lead = (dt.date.fromisoformat(event_date) - first).days * 24
                leads.append(lead)
        else:
            months = DAYS / 30
            fp += _episodes(alert_days) / months
    n_mas = sum(1 for e in events.values() if e)
    return {
        "recall": recall_hits / n_mas,
        "lead_hours_min": min(leads) if leads else 0,
        "fp_episodes_per_pm": round(fp / max(1, n_mas and
                              sum(1 for e in events.values() if not e)), 3),
    }
```

- [ ] **Step 4: 通过**——若 `lead_hours_min < 48` 或误报超标：**调规则参数而非改测试**（优先收紧 B 系最小增幅、放宽 A 系黄档），并在 references.md 记录调整依据。
- [ ] **Step 5: 全量回归 + Commit** `python -m pytest -q` 全绿后 `git commit -am "feat: W1 评测门禁（召回/提前量/误报率三指标），门禁全绿"`

---

## Self-Review 结论

1. **Spec 覆盖**：W1 范围内条目（数据层、TimeSeriesProvider、R-A/B/C、合成集、门禁三指标）均有任务；OCR/前端/离线/W4 属 W2–W4 计划，不在本文档——符合拆分。
2. **占位符**：无 TBD；Task 6 中 B5 冗余表达式已在步骤内注明修正方式。
3. **类型一致性**：`LabPoint/Checkin/RuleHit/Assessment/assess_patient/generate/gate_metrics` 签名跨任务一致；`Store.conn` 直接访问点已在 Task 8 注明替代方案。
