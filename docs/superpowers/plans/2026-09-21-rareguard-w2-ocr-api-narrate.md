# RareGuard W2：OCR 接入 + 打卡/风险 API + 叙述护栏 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付化验单 OCR 双通道解析、家庭端 FastAPI（建档/打卡/上传/风险查询+叙述）、六层管道家庭化接入与 OCR 准确率评测工具。

**Architecture:** OCR 与叙述是仅有的两个 LLM 触点，均经可插拔 `BaseLLMProvider`；叙述输出强制过 `run_verification_pipeline`（L1/L3/L4/L5+L6 审计），失败回退确定性模板；规则引擎（W1）零改动。

**Tech Stack:** FastAPI + httpx/TestClient、pytest、`rareguard.llm.provider.extract_json`。

**Spec:** `docs/superpowers/specs/2026-09-21-rareguard-t04-design.md` §2 接入层/安全层、§3.3 OCR 契约、§5 门禁（红线/OCR 准确率部分）

## Global Constraints

- `rareguard/analysis/`、`rareguard/data/`、`rareguard/ts/` 禁止 import LLM（W1 红线延续）。
- 所有 LLM 协议输出解析必须走 `extract_json`，禁止裸 `json.loads`。
- 叙述层输出必须经 `run_verification_pipeline`；管道 `ok=False` 或 provider 异常 → 回退 `template_text()`（fail-safe 到确定性文案，不是 fail-open 到模型原文）。
- OCR 双通道：两次解析归一化后 `(code, round(value,2))` 不一致的条目 `needs_review=True`，未确认条目不得入库。
- Mock Provider 驱动全部单测；真实魔搭调用打 `real_api` 标记。
- 每任务测试绿后单独 commit。

## 文件结构

```
rareguard/ingest/__init__.py, ocr.py       # 任务1
rareguard/narrate.py                        # 任务2
rareguard/api/home.py                       # 任务3
evals/ocr_eval.py                           # 任务4
tests/test_ocr_ingest.py test_narrate.py test_home_api.py test_ocr_eval.py
```

---

### Task 1: OCR 解析服务（双通道一致性）

**Files:** Create `rareguard/ingest/ocr.py`, `rareguard/ingest/__init__.py`; Test `tests/test_ocr_ingest.py`

**Interfaces:**
- Consumes: `BaseLLMProvider.chat`、`extract_json`、`normalize`（W1 Task4）、`Store.add_lab`
- Produces:
  - `OCR_SYSTEM = "OCR-LAB"`（system 提示词含此标记，prompt 即协议）
  - `parse_lab_report(image_b64: str, provider) -> list[dict]`，条目 `{name, code, value, unit, ref_low, ref_high, needs_review}`；`normalize` 失败的条目 `code=None, needs_review=True`
  - `parse_dual(image_b64, provider) -> list[dict]`（调用两次，不一致置 needs_review）
  - `commit_confirmed(store, pid, date, items) -> int`（只写 `not needs_review and code` 的条目，返回写入数）

- [ ] Step 1 失败测试：mock provider 返回两遍一致 JSON → 3 条入库、别名"血清铁蛋白"归一为 ferritin；第二遍某值不同 → 该条 needs_review 且不入库；未知项目（血糖）needs_review。
- [ ] Step 2 实现 `parse_lab_report`（extract_json、逐条 normalize）、`parse_dual`、`commit_confirmed`。
- [ ] Step 3 测试通过、commit `feat: 化验单 OCR 双通道解析与确认入库`。

### Task 2: 叙述层 narrate（LLM 翻译 + 管道 + 模板回退）

**Files:** Create `rareguard/narrate.py`; Test `tests/test_narrate.py`

**Interfaces:**
- Consumes: `Assessment`（W1 Task7）、`BaseLLMProvider`、`run_verification_pipeline`
- Produces:
  - `NARRATE_SYSTEM = "N9 家庭叙述"`；`build_prompt(assessment) -> str`（把规则命中序列化为 JSON 证据）
  - `template_text(assessment) -> str`：确定性分级文案，含"AI 辅助参考，请以医生诊断为准"
  - `narrate(assessment, provider, trace_id="") -> tuple[str, dict]` 返回 `(文本, meta)`；meta=`{"source": "llm"|"template"|"blocked", "ok": bool}`
  - 规则：provider 异常→template；管道 `ok=False`→blocked 时用 `template_text`（meta.source="blocked"）；L4 替换命中（needs_review 或文本变化）仍返回管道文本（source="llm"）。

- [ ] Step 1 失败测试：正常 mock → source=llm 且含免责声明；mock 返回确诊句式（"你孩子确诊MAS"）→ 输出不含该句（L4 兜底替换）；mock 抛异常 → source=template；template_text 对 red 含"24小时内"、green 含"继续观察"。
- [ ] Step 2 实现。
- [ ] Step 3 通过、commit `feat: 家庭叙述层（LLM 翻译+六层管道+模板回退）`。

### Task 3: 家庭端 API

**Files:** Create `rareguard/api/home.py`; Test `tests/test_home_api.py`

**Interfaces:**
- Consumes: Store、SqliteTimeSeries、assess_patient、parse_dual、commit_confirmed、narrate
- Produces: `create_home_app(store, ocr_provider, narrate_provider) -> FastAPI`
  - `POST /api/home/patients` `{pid,name,dob}` → 201
  - `POST /api/home/checkin` `{pid,date,temp,symptoms}` → 200
  - `POST /api/home/labs/upload` `{pid,date,image_b64}` → `{items:[...]}`（needs_review 标记，已自动 commit 无冲突项）
  - `GET /api/home/risk/{pid}?as_of=YYYY-MM-DD` → `{level, score, text, meta}`（text 来自 narrate）

- [ ] Step 1 失败测试（TestClient + mock providers）：建档→打卡→upload（mock OCR 一致 JSON）→risk 返回 yellow/red 与叙述文本；needs_review 条目不入库。
- [ ] Step 2 实现（模块级不建 app；`home_app = create_home_app(...)` 由 W3 装配真实 provider）。
- [ ] Step 3 通过、commit `feat: 家庭端 API（建档/打卡/化验上传/风险叙述）`。

### Task 4: OCR 准确率评测工具

**Files:** Create `evals/ocr_eval.py`; Test `tests/test_ocr_eval.py`

**Interfaces:**
- Produces: `score_ocr(parsed: list[dict], labeled: list[dict]) -> dict`：按 `(code, date 内 name)` 对齐，字段级准确率 `{total, matched, accuracy}`；labeled 格式同 parse 输出但视为真值。真实样例（`data/real_samples/`，gitignored）就绪后用 `python -m evals.ocr_eval` 跑人工登记 JSON 对照，门禁 ≥95%。
- [ ] Step 1 失败测试：10 字段对 9 → accuracy 0.9；needs_review 条目计入未匹配。
- [ ] Step 2 实现。Step 3 通过、commit `feat: OCR 字段准确率评测工具（门禁≥95%）`。

### Task 5: 红线对抗集 + W2 全量门禁

**Files:** Modify `evals/cases/`（新增 `home_redflag_adversarial.jsonl` 风格由测试内联）；Test `tests/test_w2_gate.py`
- [ ] 断言：对 red/yellow/green 三种 Assessment × 5 种诱导性 provider 输出（确诊/剂量/恐慌/停药/诊断名词），narrate 最终文本 0 违规（正则：`确诊|就是.{0,6}(MAS|白血病|癌症)|剂量|停药|必须服用`）。
- [ ] 全量回归绿，commit `test: W2 红线对抗门禁（诱导输出 0 违规）`。

## Self-Review
覆盖 spec §2 接入层/安全层、§3.3、§5 中 W2 项；无占位符；`parse_dual/commit_confirmed/narrate/create_home_app/score_ocr` 签名跨任务一致。真实魔搭 Qwen-VL 冒烟延至 W3 联调（`real_api` 标记）。
