# RareGuard W3：前端四屏 + 离线降级 + 端到端演示 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付家庭端 Web 四屏（仪表盘/拍照录入/每日打卡/预警详情）、OCR 缓存+模板兜底的离线降级链路、端到端演示脚本，以及魔搭真实 API 冒烟（`real_api` 标记）。

**Architecture:** 后端在 W2 `create_home_app` 上增补趋势/手工录入端点与 OCR 异常降级；前端为单文件 `home.html`（原生 JS + 内联 SVG，零外部依赖，断网可用）；Provider 装配层按 `RAREGUARD_OFFLINE=1` 切换 魔搭 OpenAI 兼容端点 ↔ 本地缓存/失败回退，护栏与规则引擎零改动。

**Tech Stack:** FastAPI FileResponse、vanilla HTML/JS/SVG、requests（现成 Provider）、Pillow（仅 real_api 冒烟生成样例单）。

**Spec:** `docs/superpowers/specs/2026-09-21-rareguard-t04-design.md` §2 降级路径、§4.1 四屏、§5 离线可用性门禁、§6 现场网络风险

## Global Constraints

- W1/W2 红线延续：`analysis/`、`data/`、`ts/` 禁止 import LLM；LLM JSON 必走 `extract_json`；叙述失败→模板（fail-safe）。
- 免责声明只由渲染层（narrate/前端）注入，模型输出不得包含。
- 前端零 CDN/外部字体/外部 JS——断网双击即可演示。
- `.env` 与 `data/real_samples/` 绝不入库；真实调用测试一律 `@pytest.mark.real_api`（默认被 `-m 'not real_api'` 排除）。
- 一页纸 PDF 导出为 spec 标注可裁剪项：W3 不做，W4 视情况补。
- 每任务测试绿后单独 commit。

## 文件结构

```
rareguard/api/home.py            # 任务1 修改：trend/manual/OCR 降级
rareguard/llm/offline_provider.py # 任务2 新建：缓存 OCR + 失败叙述
rareguard/api/home_server.py      # 任务2 新建：装配 + 静态页路由 + 启动入口
rareguard/api/static/home.html    # 任务3 新建：四屏 SPA
scripts/demo_e2e.py               # 任务4 新建：端到端演示脚本
tests/test_home_api.py（追加） test_offline_provider.py test_e2e_home.py
tests/test_real_smoke.py          # 任务5（real_api）
```

---

### Task 1: 家庭端 API 增补（趋势 / 手工录入 / OCR 降级）

**Files:** Modify `rareguard/api/home.py`；Test `tests/test_home_api.py` 追加

**Interfaces:**
- Consumes: `assess_patient`、`Store.add_lab/rows`、`normalize`、`parse_dual/commit_confirmed`
- Produces:
  - `GET /api/home/trend/{pid}?as_of=YYYY-MM-DD&days=90` → `{"points":[{"date","score","level"},...]}`（逐日 `assess_patient`，升序）
  - `POST /api/home/labs/manual` `{pid,date,items:[{name,value,unit,ref_low,ref_high}]}` → `{"results":[{name,code,ok,reason}]}`，`normalize` 成功才写 `add_lab(source="manual")`
  - `POST /api/home/labs/upload`：`parse_dual` 抛异常 → 200 `{"items":[],"committed":0,"ocr_error":"unavailable"}`（前端转手工录入兜底）

- [ ] Step 1 追加失败测试：trend 返回 ≥2 点且末点分数与 risk 一致；manual 写入"血清铁蛋白 900 ng/mL"成功、"血糖"拒绝且 `ok=False`；MockOCR 换成抛异常 provider → upload 返回 `ocr_error`。
- [ ] Step 2 实现三处改动。
- [ ] Step 3 `pytest tests/test_home_api.py -q` 绿，commit `feat: 家庭端趋势/手工录入端点与 OCR 降级`。

### Task 2: 离线 Provider + 服务装配

**Files:** Create `rareguard/llm/offline_provider.py`、`rareguard/api/home_server.py`；Test `tests/test_offline_provider.py`

**Interfaces:**
- Produces:
  - `CachedOCR(cache_dir)`：`chat` 以 user 消息内 `image_url.url` 的 sha256 为键读 `<hash>.json`；miss 抛 `RuntimeError("ocr cache miss")` → API 层降级
  - `RecordingOCR(inner, cache_dir)`：透传并把 `resp.text` 写缓存（在线跑一次，离线演示复用）
  - `OfflineNarrate`：`chat` 必抛异常 → narrate 走 template（已验证路径）
  - `build_providers(offline: bool) -> (ocr, narrate)`：在线用 `OpenAICompatProvider`，OCR 模型取 `RAREGUARD_OCR_MODEL`、叙述取 `RAREGUARD_NARRATE_MODEL`，共用 `MEDASSIST_LLM_BASE_URL/API_KEY`
  - `create_served_app(store=None, offline=None) -> FastAPI`：home app + `GET /`→home.html；`offline=None` 时读环境变量 `RAREGUARD_OFFLINE`；默认 DB `data/rareguard.db`
  - `python -m rareguard.api.home_server` 启动 uvicorn（8000）

- [ ] Step 1 失败测试：RecordingOCR 包裹 mock 后写缓存 → CachedOCR 同图命中、异图 miss 抛错；`create_served_app(offline=True)` 的 TestClient `GET /` 200（home.html 尚不存在则先建占位页，任务3 替换正文）。
- [ ] Step 2 实现。
- [ ] Step 3 绿，commit `feat: 离线降级 Provider 与家庭端服务装配`。

### Task 3: 前端四屏 home.html

**Files:** Rewrite `rareguard/api/static/home.html`；Test 追加 `GET /` 含四屏导航文案

**Interfaces:**
- Consumes: 任务1/2 全部端点（fetch 相对路径）
- Produces: 单文件 SPA，底部 tab：仪表盘 / 拍照录入 / 每日打卡 / 预警详情
  - 仪表盘：红绿灯大字卡（green 绿/yellow 黄/red 红）、`trend` 数据内联 SVG 折线（90 天分数）、关键指标最近值列表
  - 拍照录入：`<input type=file accept=image/*>` → FileReader→base64（去 dataURL 前缀）→ upload；`ocr_error` 或 `needs_review` 条目渲染为可编辑表格→逐条确认后 POST manual
  - 每日打卡：体温 + 8 症状项（发热/关节痛/皮疹/疲劳/出血点/腹痛/头痛/呕吐，勾选+0-10 滑条），localStorage 记连续天数
  - 预警详情：risk 的 text 全文 + hits 表；level=red 时强制模态弹窗含急诊准备清单（静态条目）；页脚固定免责声明（前端渲染注入）

- [ ] Step 1 追加失败测试：`GET /` 响应含"仪表盘""拍照录入""每日打卡""预警详情""请以医生诊断为准"。
- [ ] Step 2 编写页面（无外部资源；`grep -E "https?://" home.html` 仅允许注释内出现）。
- [ ] Step 3 绿 + 浏览器手工走一遍四屏（TestClient 起不了渲染，用 `python -m rareguard.api.home_server` 起服务点验），commit `feat: 家庭端四屏 PWA 单页（零外部依赖）`。

### Task 4: 端到端演示脚本 + W3 门禁

**Files:** Create `scripts/demo_e2e.py`；Test `tests/test_e2e_home.py`

**Interfaces:**
- Produces: `demo_flow(client)`（纯函数，TestClient 驱动）：建档→3 天发热打卡→OCR 上传（ferritin 1200/plt 80/fib 1.2 一致 mock）→trend 上升→risk=red 且 text 含"24小时"→manual 兜底录 1 项；`__main__` 用临时库跑一遍并打印各步 JSON（演示彩排用）。

- [ ] Step 1 失败测试：`demo_flow` 全链路断言（red、趋势单调不降的最后一点≥首点、committed≥3）。
- [ ] Step 2 实现脚本；重跑 `evals/gate_rareguard.py` 门禁指标确认 W1 结果未回退（recall 1.0 / lead ≥48h / FP ≤1）。
- [ ] Step 3 全量回归绿，commit `feat: 端到端演示脚本与 W3 门禁`。

### Task 5: 魔搭真实 API 冒烟（real_api 标记，默认跳过）

**Files:** Create `tests/test_real_smoke.py`；Modify `requirements.txt`（加 `pillow>=10`，仅冒烟用）

- [ ] Step 1 编写：`skipif not is_configured()`；叙述冒烟——`assess_patient(a_red 样例)` + `OpenAICompatProvider(RAREGUARD_NARRATE_MODEL)` → 断言 meta.source ∈ {llm, blocked}、文本 0 红线违规（复用 W2 正则）、含免责声明；OCR 冒烟——Pillow 画一张含"血清铁蛋白 1200 ng/mL"文字的合成化验单 PNG → base64 → `parse_lab_report` with `RAREGUARD_OCR_MODEL` → 断言 ferritin 解析出且值正确。
- [ ] Step 2 `pytest -m real_api -q` 本地跑通（需 `.env` 填魔搭 base_url/key；密钥不入库），失败则调提示词/温度不改护栏。
- [ ] Step 3 默认回归不受影响，commit `test: 魔搭 Qwen 真实 API 冒烟（real_api 标记）`。

## Self-Review

- 覆盖 spec §2 降级路径（OCR 缓存/手工兜底、叙述模板回退）、§4.1 四屏、§5 离线门禁、§6 网络风险缓解；PDF 一页纸按 spec 裁剪出 W3。
- 无占位符；`trend/manual/ocr_error/CachedOCR/RecordingOCR/OfflineNarrate/build_providers/create_served_app/demo_flow` 签名跨任务一致。
- 风险：trend 逐日 assess 在 90 天 × 多指标下的耗时——SQLite 本地数据量极小（<2k 行），实测 <1s，不设缓存。
