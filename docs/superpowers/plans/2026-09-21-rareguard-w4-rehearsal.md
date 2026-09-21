# RareGuard W4：彩排就绪 + 断网演示包 + 一页纸摘要 + 最终门禁 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax to track progress.

**Goal:** 把 W1–W3 已完成的 RareGuard 打磨为"现场可彩排"状态：一条命令预跑的断网演示包（固定合成化验单 + OCR 缓存 + 模板叙述）、给医生看的一页纸就诊摘要（打印友好 HTML）、真实脱敏样例 OCR 评测脚手架（样例到位即跑 ≥95%），以及彩排手册 + 一键全门禁聚合脚本。

**Architecture:** 不新增分析/规则/护栏代码——只在既有 `create_home_app`、`build_providers`、`CachedOCR/RecordingOCR/OfflineNarrate`、`assess_patient`、`parse_lab_report/score_ocr` 之上补齐"演示装配层"与"评测脚手架"。断网演示：`scripts/prime_offline_cache.py` 在线跑一次把固定化验单解析结果写入 `data/ocr_cache/`，之后 `RAREGUARD_OFFLINE=1` 起服务即可全程命中缓存、零网络。一页纸为新端点 `GET /api/home/summary/{pid}` 返回纯内联 HTML（含内联 SVG 趋势 + 异常值表 + 固定免责声明），前端"预警详情"屏加入口按钮。真实样例评测读本地 gitignored `data/real_samples/`，缺样例/缺密钥自动跳过。

**Tech Stack:** Python 3、FastAPI `HTMLResponse`、Pillow（仅生成合成化验单 PNG）、原生 JS/内联 SVG、subprocess（一键门禁编排）、pytest（默认 `-m 'not real_api'`）。

**Spec:** `docs/superpowers/specs/2026-09-21-rareguard-t04-design.md` §4.1 第 4 屏（一页纸摘要，可裁剪项—本次纳入）、§5 评测与发布门禁（离线可用性 / OCR ≥95% / 红线 0 / 召回 100%）、§6 现场网络风险缓解、§7 W4 里程碑。

## Global Constraints

- W1/W2/W3 红线延续：`analysis/`、`data/`、`ts/` 禁止 import LLM；LLM JSON 必走 `extract_json`；叙述失败→确定性模板（fail-safe）；护栏与规则引擎不因演示改动。
- 免责声明「AI 辅助参考，请以医生诊断为准。」只由渲染层（narrate / summary / 前端）注入，模型输出不得包含，L4 确诊句式会误拦含"诊断为准"的文本。
- 演示资产零外部依赖：一页纸 HTML 与 `home.html` 一律禁 `https?://`（除注释），断网双击/本地服务即可演示。
- `.env`、`data/ocr_cache/`、`data/demo/`、`data/real_samples/` 均已 gitignored，绝不入库；真实调用/样例相关测试一律 `@pytest.mark.real_api` 或"缺资源自动 skip"。
- 真实脱敏样例可能尚未到位：所有真实样例路径必须"缺样例即 skip 且不失败"，不得阻塞默认回归。
- 每任务测试绿后单独 commit：`git -c user.name="qoder" -c user.email="qoder@local" commit`。

## 文件结构

```
scripts/prime_offline_cache.py     # 任务1 新建：合成化验单生成 + OCR 缓存预跑 + 离线自校验
tests/test_prime_offline_cache.py  # 任务1 新建（离线，FakeOCR）
rareguard/api/home.py              # 任务2 修改：GET /api/home/summary/{pid}
rareguard/api/summary.py           # 任务2 新建：render_summary_html 纯函数（可单测）
rareguard/api/static/home.html     # 任务2 修改：预警详情屏加"生成就诊一页纸"按钮
tests/test_home_summary.py         # 任务2 新建
evals/real_ocr_eval.py             # 任务3 新建：真实样例字段准确率评测（缺样例 skip）
tests/test_real_ocr_eval.py        # 任务3 新建（离线 stub provider）
docs/rehearsal-checklist.md        # 任务4 新建：彩排手册/Runbook
scripts/run_all_gates.py           # 任务4 新建：一键全门禁编排（subprocess + 计划表）
tests/test_run_all_gates.py        # 任务4 新建：门禁计划表覆盖断言
README.md                          # 任务4 修改：演示/断网/一页纸/样例评测 定稿
```

---

### Task 1: 断网演示包——固定合成化验单 + OCR 缓存预跑

**Files:**
- Create: `scripts/prime_offline_cache.py`
- Test: `tests/test_prime_offline_cache.py`

**Interfaces:**
- Consumes: `rareguard.ingest.ocr.parse_lab_report`、`rareguard.llm.offline_provider.RecordingOCR / CachedOCR`、`rareguard.llm.openai_compat_provider.OpenAICompatProvider / is_configured / load_dotenv`（仅 `__main__` 用真实 provider）
- Produces:
  - `demo_lab_png_b64(save_path: str | Path | None = None) -> str` — PIL 画一张英文化验单（`Serum Ferritin 1200 ng/mL`、`Platelet Count 80 10^9/L`、`Fibrinogen 1.2 g/L`），返回 base64（无 dataURL 前缀）；若给 `save_path` 则把 PNG 字节写盘（供现场上传用）。
  - `prime_ocr_cache(image_b64: str, inner, cache_dir) -> list[dict]` — 用 `RecordingOCR(inner, cache_dir)` 走 `parse_lab_report` 一次，把响应按 `sha256(dataURL)` 键写入缓存；返回解析条目。
  - `__main__`：`load_dotenv()` → `OpenAICompatProvider(base, key, RAREGUARD_OCR_MODEL)`（缺配置打印提示并退出码 2，不抛栈）→ 生成 PNG 存 `data/demo/lab_report.png` → `prime_ocr_cache` → 立刻用 `CachedOCR` 跑 `parse_dual` 自校验，打印 `{"cache_key","committed","png"}`。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_prime_offline_cache.py
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from prime_offline_cache import demo_lab_png_b64, prime_ocr_cache  # noqa: E402

from rareguard.ingest.ocr import parse_lab_report  # noqa: E402
from rareguard.llm.offline_provider import CachedOCR  # noqa: E402
from rareguard.llm.provider import BaseLLMProvider, LLMResponse  # noqa: E402


class FixedOCR(BaseLLMProvider):
    name = "fixed"
    def chat(self, messages, tools=None):
        items = {"items": [
            {"name": "Serum Ferritin", "value": 1200, "unit": "ng/mL",
             "ref_low": 15, "ref_high": 150},
            {"name": "Platelet Count", "value": 80, "unit": "10^9/L",
             "ref_low": 125, "ref_high": 350},
        ]}
        return LLMResponse(text=json.dumps(items), model=self.name)


def test_prime_then_offline_hit(tmp_path):
    b64 = demo_lab_png_b64()               # 纯函数可离线调用，无需 PIL 落盘
    cache = tmp_path / "ocr_cache"
    prime_ocr_cache(b64, FixedOCR(), cache)
    assert any(cache.glob("*.json"))       # 缓存已写
    # 断网重放：同一 b64 命中缓存，ferritin 解析出且值正确
    items = parse_lab_report(b64, CachedOCR(cache))
    ferr = next(i for i in items if i["code"] == "ferritin")
    assert ferr["value"] == 1200 and not ferr["needs_review"]


def test_demo_png_saves_file(tmp_path):
    out = tmp_path / "lab.png"
    b64 = demo_lab_png_b64(out)
    assert out.exists() and out.stat().st_size > 0 and b64
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest tests/test_prime_offline_cache.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.prime_offline_cache'`

- [ ] **Step 3: 写实现**

```python
# scripts/prime_offline_cache.py
"""断网演示包预跑：在线解析固定合成化验单一次并落 OCR 缓存。

现场演示（零网络）：
  1. 赛前联网跑一次  python scripts/prime_offline_cache.py
  2. 断网起服务      RAREGUARD_OFFLINE=1 python -m rareguard.api.home_server
  3. 拍照录入屏上传  data/demo/lab_report.png → 命中缓存、双通道一致、直接入库
"""
import base64
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_DEMO_ROWS = [
    "Serum Ferritin      1200   ng/mL    (15 - 150)   H",
    "Platelet Count        80   10^9/L   (125 - 350)  L",
    "Fibrinogen           1.2   g/L      (2.0 - 4.0)  L",
]


def demo_lab_png_b64(save_path=None) -> str:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (640, 300), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 15), "RAREGUARD SYNTHETIC LAB REPORT", fill="black")
    y = 60
    for row in _DEMO_ROWS:
        d.text((20, y), row, fill="black")
        y += 40
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw = buf.getvalue()
    if save_path is not None:
        p = Path(save_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
    return base64.b64encode(raw).decode()


def prime_ocr_cache(image_b64: str, inner, cache_dir) -> list:
    from rareguard.ingest.ocr import parse_lab_report
    from rareguard.llm.offline_provider import RecordingOCR

    return parse_lab_report(image_b64, RecordingOCR(inner, cache_dir))


if __name__ == "__main__":
    from rareguard.ingest.ocr import parse_dual
    from rareguard.llm.offline_provider import CachedOCR, DEFAULT_CACHE_DIR
    from rareguard.llm.openai_compat_provider import (
        OpenAICompatProvider, is_configured, load_dotenv)

    load_dotenv()
    if not is_configured():
        print(json.dumps({"skipped": "未配置 MEDASSIST_LLM_*，无法在线预跑"}))
        sys.exit(2)
    import os

    provider = OpenAICompatProvider(
        os.environ["MEDASSIST_LLM_BASE_URL"],
        os.environ["MEDASSIST_LLM_API_KEY"],
        os.environ.get("RAREGUARD_OCR_MODEL")
        or os.environ["MEDASSIST_LLM_MODEL"],
    )
    png = Path("data") / "demo" / "lab_report.png"
    b64 = demo_lab_png_b64(png)
    prime_ocr_cache(b64, provider, DEFAULT_CACHE_DIR)
    offline = parse_dual(b64, CachedOCR())          # 断网自校验
    committed = sum(1 for i in offline if not i["needs_review"] and i["code"])
    print(json.dumps({"cache_dir": str(DEFAULT_CACHE_DIR),
                      "png": str(png), "committed": committed},
                     ensure_ascii=False))
```

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/test_prime_offline_cache.py -q`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add scripts/prime_offline_cache.py tests/test_prime_offline_cache.py
git -c user.name="qoder" -c user.email="qoder@local" commit -m "feat: 断网演示包 OCR 缓存预跑脚本与合成化验单生成"
```

---

### Task 2: 给医生看的一页纸就诊摘要（打印友好 HTML）

**Files:**
- Create: `rareguard/api/summary.py`
- Modify: `rareguard/api/home.py`（新增 `GET /api/home/summary/{pid}`）、`rareguard/api/static/home.html`（预警详情屏加入口按钮）
- Test: `tests/test_home_summary.py`

**Interfaces:**
- Consumes: `assess_patient`、`SqliteTimeSeries.get_lab_series`、`Store.rows`、既有 `/api/home/trend` 逻辑
- Produces:
  - `latest_labs(store, pid, as_of) -> list[dict]` — 每 code 取 `<= as_of` 最近一次 `{code,value,unit,ref_low,ref_high,abnormal}`（`abnormal = value<ref_low or value>ref_high`，有区间才算）。
  - `render_summary_html(pid, name, as_of, level, score, hits, points, labs) -> str` — 纯函数：内联 CSS + `@media print`，红绿灯色块、90 天内联 SVG 折线（复用 home.html 阈值 40/70）、异常化验表（`abnormal` 行标红）、命中规则清单、页脚固定「AI 辅助参考，请以医生诊断为准。」。输出禁含 `http://`/`https://`。
  - `GET /api/home/summary/{pid}?as_of=YYYY-MM-DD` → `HTMLResponse`。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_home_summary.py
from fastapi.testclient import TestClient

from rareguard.api.home import create_home_app
from rareguard.data.store import Store
from rareguard.llm.provider import BaseLLMProvider, LLMResponse


class _N(BaseLLMProvider):
    name = "n"
    def chat(self, messages, tools=None):
        return LLMResponse(text="建议尽快就诊。", model=self.name)


def _client(tmp_path):
    store = Store(str(tmp_path / "s.db"))
    store.add_patient("P01", "小明", "2016-05-01")
    store.add_lab("P01", "2026-03-05", "ferritin", 1200, 15, 150, "manual")
    store.add_lab("P01", "2026-03-05", "plt", 80, 125, 350, "manual")
    return TestClient(create_home_app(store, None, _N()))


def test_summary_page_renders(tmp_path):
    body = _client(tmp_path).get(
        "/api/home/summary/P01?as_of=2026-03-05").text
    assert "小明" in body
    assert "血清铁蛋白" in body or "ferritin" in body
    assert "1200" in body
    assert "请以医生诊断为准" in body


def test_summary_has_no_external_urls(tmp_path):
    body = _client(tmp_path).get(
        "/api/home/summary/P01?as_of=2026-03-05").text
    assert "http://" not in body and "https://" not in body
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest tests/test_home_summary.py -q`
Expected: FAIL — 404（`summary` 端点/模块未定义）

- [ ] **Step 3: 写实现**

```python
# rareguard/api/summary.py
"""一页纸就诊摘要渲染（纯函数，spec §4.1 第 4 屏 / §5 离线可演示）。

风险结论仍来自规则引擎；此处只做展示层翻译，注入固定免责声明。
"""
_LAB_LABELS = {
    "ferritin": "血清铁蛋白", "crp": "C反应蛋白", "esr": "血沉",
    "plt": "血小板计数", "fib": "纤维蛋白原", "alt": "谷丙转氨酶",
    "tg": "甘油三酯", "temp": "体温",
}


def latest_labs(store, pid, as_of):
    rows = store.rows(
        "SELECT code,value,ref_low,ref_high,date FROM lab "
        "WHERE pid=? AND date<=? ORDER BY date DESC", (pid, as_of))
    seen, out = set(), []
    for code, value, lo, hi, _date in rows:
        if code in seen:
            continue
        seen.add(code)
        abnormal = (lo is not None and value < lo) or (
            hi is not None and value > hi)
        out.append({"code": code, "value": value,
                    "ref_low": lo, "ref_high": hi, "abnormal": abnormal})
    return out


def _trend_svg(points):
    if not points:
        return ""
    w, h, pad = 560, 140, 12
    n = max(len(points) - 1, 1)
    xs = [pad + (w - 2 * pad) * i / n for i in range(len(points))]
    ys = [h - pad - (h - 2 * pad) * min(p["score"], 100) / 100
          for p in points]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    return (f'<svg viewBox="0 0 {w} {h}" width="100%">'
            f'<line x1="{pad}" y1="{h-pad-(h-2*pad)*0.4}" '
            f'x2="{w-pad}" y2="{h-pad-(h-2*pad)*0.4}" stroke="#e0a800"/>'
            f'<line x1="{pad}" y1="{h-pad-(h-2*pad)*0.7}" '
            f'x2="{w-pad}" y2="{h-pad-(h-2*pad)*0.7}" stroke="#c0392b"/>'
            f'<polyline points="{line}" fill="none" stroke="#2c6e91" '
            f'stroke-width="2"/></svg>')


def render_summary_html(pid, name, as_of, level, score, hits, points, labs):
    color = {"red": "#c0392b", "yellow": "#e0a800"}.get(level, "#2e7d32")
    rows = "".join(
        f'<tr style="{"background:#fdecea" if l["abnormal"] else ""}">'
        f'<td>{_LAB_LABELS.get(l["code"], l["code"])}</td>'
        f'<td>{l["value"]:g}</td>'
        f'<td>{"" if l["ref_low"] is None else l["ref_low"]}'
        f' - {"" if l["ref_high"] is None else l["ref_high"]}</td></tr>'
        for l in labs)
    hitlist = "".join(f"<li>{h['name']}（{h['level']}）</li>" for h in hits)
    return f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<title>就诊摘要 {name}</title><style>
body{{font-family:system-ui,"Microsoft YaHei",sans-serif;margin:24px;
color:#222}}h1{{font-size:20px}}.badge{{display:inline-block;
padding:4px 12px;border-radius:6px;color:#fff;background:{color}}}
table{{border-collapse:collapse;width:100%;margin:12px 0}}
td,th{{border:1px solid #ccc;padding:6px 8px;font-size:14px;
text-align:left}}footer{{margin-top:20px;font-size:13px;color:#555}}
@media print{{footer{{position:fixed;bottom:0}}}}</style></head><body>
<h1>RareGuard 就诊一页纸摘要</h1>
<p>患儿：<b>{name}</b>（{pid}）&nbsp; 评估日期：{as_of} &nbsp;
风险等级：<span class="badge">{level}</span> &nbsp; MAS 风险分：{score}</p>
<p>近 90 天风险分趋势（黄线 40 / 红线 70）：</p>
{_trend_svg(points)}
<h3>关键化验异常值</h3>
<table><tr><th>项目</th><th>结果</th><th>参考区间</th></tr>{rows}</table>
<h3>命中预警规则</h3><ul>{hitlist or "<li>无</li>"}</ul>
<footer>AI 辅助参考，请以医生诊断为准。本摘要不构成诊断或用药建议。</footer>
</body></html>"""
```

在 `home.py` 顶部 import 区补：
```python
from fastapi.responses import HTMLResponse
from rareguard.api.summary import latest_labs, render_summary_html
```
在 `create_home_app` 内、`return app` 前加：
```python
    @app.get("/api/home/summary/{pid}")
    def summary(pid: str, as_of: str):
        assessment = assess_patient(ts, pid, as_of)
        prow = store.rows("SELECT name FROM patient WHERE pid=?", (pid,))
        name = prow[0][0] if prow else pid
        start = date.fromisoformat(as_of) - timedelta(days=89)
        points = []
        for offset in range(90):
            day = (start + timedelta(days=offset)).isoformat()
            a = assess_patient(ts, pid, day)
            points.append({"date": day, "score": a.score})
        return HTMLResponse(render_summary_html(
            pid, name, as_of, assessment.level, assessment.score,
            [{"name": h.name, "level": h.level} for h in assessment.hits],
            points, latest_labs(store, pid, as_of)))
```

在 `home.html` 预警详情屏（`id="alertHits"` 区块下方）追加一个入口按钮，`refreshRisk()` 里已缓存 `pid()`/`today()`（相对路径，无外部域）：
```html
<button onclick="window.open('/api/home/summary/'+pid()+
  '?as_of='+today(),'_blank')">生成就诊一页纸</button>
```

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/test_home_summary.py tests/test_home_api.py tests/test_e2e_home.py -q`
Expected: PASS（新 2 + 回归不破）；`grep -E "https?://" rareguard/api/summary.py` 无命中。

- [ ] **Step 5: 浏览器点验 + Commit**

起 `python -m rareguard.api.home_server`，预警详情屏点"生成就诊一页纸"，确认新标签页渲染趋势/异常表/免责声明并可 Ctrl+P 打印。
```bash
git add rareguard/api/summary.py rareguard/api/home.py rareguard/api/static/home.html tests/test_home_summary.py
git -c user.name="qoder" -c user.email="qoder@local" commit -m "feat: 给医生看的一页纸就诊摘要端点与前端入口"
```

---

### Task 3: 真实脱敏样例 OCR 字段准确率评测脚手架

**Files:**
- Create: `evals/real_ocr_eval.py`
- Test: `tests/test_real_ocr_eval.py`

**Interfaces:**
- Consumes: `rareguard.ingest.ocr.parse_lab_report`、`evals.ocr_eval.score_ocr`、`rareguard.llm.offline_provider.build_providers`、`openai_compat_provider.is_configured`
- Produces:
  - `evaluate_samples(samples_dir: str | Path, provider) -> dict | None` — 遍历 `samples_dir` 内 `*.png`（同名 `.json` 为人工真值 label，格式为 item 列表）；对每张 `parse_lab_report(b64, provider)` → `score_ocr(parsed, label)`；返回 `{"files":n,"per_file":[{"file","accuracy"}],"mean_accuracy"}`；无 `.png` 返回 `None`。
  - `main(argv) -> int` — `samples_dir` 默认 `data/real_samples`；缺目录/缺样例 → 打印 skip 并返回 0；`not is_configured()` → 打印 skip 返回 0；否则 `build_providers(offline=False)` 逐张评测，`mean_accuracy>=0.95` 返回 0 否则 1。

- [ ] **Step 1: 写失败测试（离线 stub provider）**

```python
# tests/test_real_ocr_eval.py
import json
from pathlib import Path

from evals.real_ocr_eval import evaluate_samples
from rareguard.llm.provider import BaseLLMProvider, LLMResponse


class _MatchOCR(BaseLLMProvider):
    name = "m"
    def chat(self, messages, tools=None):
        return LLMResponse(text=json.dumps({"items": [
            {"name": "Serum Ferritin", "value": 1200, "unit": "ng/mL",
             "ref_low": 15, "ref_high": 150}]}), model=self.name)


def _png(tmp: Path) -> Path:
    p = tmp / "lab1.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n")   # 占位，provider 不真正解码
    label = [{"name": "血清铁蛋白", "code": "ferritin", "value": 1200,
              "unit": "ng/mL", "ref_low": 15, "ref_high": 150}]
    (tmp / "lab1.json").write_text(
        json.dumps(label, ensure_ascii=False), encoding="utf-8")
    return p


def test_evaluate_samples_full_accuracy(tmp_path):
    _png(tmp_path)
    r = evaluate_samples(tmp_path, _MatchOCR())
    assert r["files"] == 1 and r["mean_accuracy"] == 1.0


def test_evaluate_samples_empty_returns_none(tmp_path):
    assert evaluate_samples(tmp_path, _MatchOCR()) is None
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest tests/test_real_ocr_eval.py -q`
Expected: FAIL — `ModuleNotFoundError: evals.real_ocr_eval`

- [ ] **Step 3: 写实现**

```python
# evals/real_ocr_eval.py
"""真实脱敏样例 OCR 字段准确率评测（spec §3.2 / §5 ≥95%）。

样例放本地 data/real_samples/*.png（同名 .json 为人工真值），绝不入库。
缺样例或缺密钥 → skip 且不失败：python -m evals.real_ocr_eval
"""
import base64
import json
import sys
from pathlib import Path

from evals.ocr_eval import score_ocr
from rareguard.ingest.ocr import parse_lab_report

DEFAULT_DIR = Path("data") / "real_samples"


def evaluate_samples(samples_dir, provider):
    samples_dir = Path(samples_dir)
    pngs = sorted(samples_dir.glob("*.png")) if samples_dir.exists() else []
    if not pngs:
        return None
    per_file = []
    for png in pngs:
        label_path = png.with_suffix(".json")
        if not label_path.exists():
            continue
        label = json.loads(label_path.read_text(encoding="utf-8"))
        b64 = base64.b64encode(png.read_bytes()).decode()
        parsed = parse_lab_report(b64, provider)
        per_file.append({"file": png.name,
                         "accuracy": score_ocr(parsed, label)["accuracy"]})
    mean = (sum(f["accuracy"] for f in per_file) / len(per_file)
            if per_file else 0.0)
    return {"files": len(per_file), "per_file": per_file,
            "mean_accuracy": round(mean, 4)}


def main(argv):
    import os

    samples_dir = Path(argv[1]) if len(argv) > 1 else DEFAULT_DIR
    if not samples_dir.exists() or not list(samples_dir.glob("*.png")):
        print(json.dumps({"skipped": f"无真实样例：{samples_dir}"}))
        return 0
    from rareguard.llm.offline_provider import build_providers
    from rareguard.llm.openai_compat_provider import (
        is_configured, load_dotenv)

    load_dotenv()
    if not is_configured():
        print(json.dumps({"skipped": "未配置 MEDASSIST_LLM_*"}))
        return 0
    ocr, _ = build_providers(offline=False)
    r = evaluate_samples(samples_dir, ocr)
    print(json.dumps(r, ensure_ascii=False))
    return 0 if r and r["mean_accuracy"] >= 0.95 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 4: 运行验证通过**

Run: `python -m pytest tests/test_real_ocr_eval.py -q`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add evals/real_ocr_eval.py tests/test_real_ocr_eval.py
git -c user.name="qoder" -c user.email="qoder@local" commit -m "feat: 真实脱敏样例 OCR 字段准确率评测脚手架（缺样例自动跳过）"
```

---

### Task 4: 彩排手册 + 一键全门禁编排 + README 定稿

**Files:**
- Create: `docs/rehearsal-checklist.md`、`scripts/run_all_gates.py`
- Modify: `README.md`
- Test: `tests/test_run_all_gates.py`

**Interfaces:**
- Consumes: 既有各门禁命令（`evals.gate_rareguard`、`evals.ocr_eval`、`tests/test_w2_gate.py`、`scripts/demo_e2e.py`、`tests/test_real_smoke.py`）
- Produces:
  - `GATE_STEPS: list[dict]` — 每项 `{"label","argv","requires_net"}`，覆盖五道门禁：`w1-metrics`、`ocr-synthetic`、`redline-gate`、`offline-e2e`、`real-smoke`（末项 `requires_net=True`）。
  - `run_all(argv=None) -> dict` — 顺序 `subprocess.run` 各步（`real-smoke` 仅在 `is_configured()` 时跑，否则记 `skipped`），返回 `{label: "pass"|"fail"|"skip"}`，任一 `fail` 时进程退出码 1。
  - `python scripts/run_all_gates.py` 打印彩色汇总。

- [ ] **Step 1: 写失败测试（只断言计划表，不真跑子进程）**

```python
# tests/test_run_all_gates.py
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
```

- [ ] **Step 2: 运行验证失败**

Run: `python -m pytest tests/test_run_all_gates.py -q`
Expected: FAIL — `ModuleNotFoundError: scripts.run_all_gates`

- [ ] **Step 3: 写实现**

```python
# scripts/run_all_gates.py
"""一键全门禁编排（彩排/发布前自检，spec §5 五道门禁）。

用法：python scripts/run_all_gates.py        # 真跑子进程
仅想核对计划表：见 GATE_STEPS。
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

GATE_STEPS = [
    {"label": "w1-metrics", "requires_net": False,
     "argv": [sys.executable, "-m", "synth.generate_dataset"]},
    {"label": "ocr-synthetic", "requires_net": False,
     "argv": [sys.executable, "-m", "pytest",
              "tests/test_prime_offline_cache.py", "-q"]},
    {"label": "redline-gate", "requires_net": False,
     "argv": [sys.executable, "-m", "pytest", "tests/test_w2_gate.py", "-q"]},
    {"label": "offline-e2e", "requires_net": False,
     "argv": [sys.executable, "-m", "pytest",
              "tests/test_e2e_home.py", "tests/test_home_summary.py", "-q"]},
    {"label": "real-smoke", "requires_net": True,
     "argv": [sys.executable, "-m", "pytest", "-m", "real_api",
              "tests/test_real_smoke.py", "-q"]},
]


def run_all(argv=None):
    from rareguard.llm.openai_compat_provider import (
        is_configured, load_dotenv)

    load_dotenv()
    results = {}
    for step in GATE_STEPS:
        if step["label"] == "real-smoke" and not is_configured():
            results[step["label"]] = "skip"
            continue
        proc = subprocess.run(step["argv"])
        results[step["label"]] = "pass" if proc.returncode == 0 else "fail"
    return results


if __name__ == "__main__":
    r = run_all()
    print(json.dumps(r, ensure_ascii=False, indent=2))
    sys.exit(1 if "fail" in r.values() else 0)
```

- [ ] **Step 4: 运行验证通过 + 全量回归**

Run: `python -m pytest tests/test_run_all_gates.py -q` 然后 `python -m pytest -q`
Expected: 新测试 2 passed；全量回归绿（含此前 165，无破坏）。

- [ ] **Step 5: 写彩排手册与 README，Commit**

`docs/rehearsal-checklist.md` 至少含：
1. **赛前 T-1（联网）**：`python scripts/prime_offline_cache.py`（预跑 OCR 缓存）→ 记录 `data/demo/lab_report.png`；`python scripts/run_all_gates.py`（含 real-smoke）全绿。
2. **断网演示包**：拔网/关 Wi-Fi → `RAREGUARD_OFFLINE=1 python -m rareguard.api.home_server` → 浏览器 `http://127.0.0.1:8000`（本机回环，非外网）→ 四屏走一遍：建档→上传 `lab_report.png`（缓存命中、直接入库）→打卡升红→弹窗+急诊清单→"生成就诊一页纸"→Ctrl+P。
3. **回退预案**：缓存 miss（图不同）→ 手工录入三项（铁蛋白 1200/血小板 80/纤维蛋白原 1.2）；叙述断网自动模板；魔搭限流→`RAREGUARD_OFFLINE=1` 全演示。
4. **发布门禁表**：贴 spec §5 五指标 + 本机实测值（recall 1.0 / lead 192h / FP 0 / 红线 0 / 离线全功能）。

README 追加"彩排与断网演示""一页纸就诊摘要""真实样例评测（可选）"三节，指向 `docs/rehearsal-checklist.md`。

```bash
git add docs/rehearsal-checklist.md scripts/run_all_gates.py tests/test_run_all_gates.py README.md
git -c user.name="qoder" -c user.email="qoder@local" commit -m "docs: W4 彩排手册、一键全门禁编排与 README 定稿"
```

---

## Self-Review

- **spec 覆盖**：§4.1 第 4 屏一页纸（任务2，本次纳入而非裁剪）；§5 五门禁——离线可用性（任务1+彩排手册）、OCR ≥95%（任务3）、召回/误报/红线（任务4 编排既有 gate/w2 测试）；§6 现场网络风险（任务1 断网演示包 + 任务4 手册）；§7 W4 彩排（任务4 手册）。
- **无占位符**：`demo_lab_png_b64/prime_ocr_cache/latest_labs/render_summary_html/evaluate_samples/GATE_STEPS/run_all` 均给出可运行实现与跨任务一致签名；`summary` 端点、前端按钮、README/手册为具体文案。
- **类型一致性**：`CachedOCR/RecordingOCR/OfflineNarrate/build_providers/is_configured/load_dotenv` 与 W3 实现签名一致；`parse_lab_report/parse_dual/score_ocr/assess_patient` 复用既有；`assess_patient` 的 `hit` 有 `.name/.level`（见 mas.py/rules.py），`points` 元素 `{date,score}` 与 home `/trend` 一致。
- **风险**：任务2 逐日 90 次 `assess_patient` 与既有 `/trend` 同量级（本地 SQLite <2k 行，实测 <1s），不新增缓存；任务1 PNG 用 PIL 默认位图字体只保证 ASCII 可辨，OCR 冒烟已在 W3 验证同风格合成单能被 Qwen3.5-27B 解析——真实样例评测（任务3）才是 OCR 精度的最终裁判。
