# RareGuard 现场彩排手册（W4 Runbook）

面向 2026.10.15–10.17 杭州·南湖未来科学园路演的操作清单。核心红线：**风险结论只出自确定性规则引擎，断网照常出预警**；LLM 仅翻译表达。

## 0. 一键自检（发布/彩排前必跑）

```bash
python scripts/run_all_gates.py
```

期望输出五道门禁全 `pass`（未配魔搭密钥时 `real-smoke` 记 `skip`）：

| 门禁 | 命令映射 | 阈值 |
|---|---|---|
| w1-metrics | `tests/test_gate_rareguard.py` | 召回 1.0 / 提前 ≥48h / 误报 ≤1 |
| ocr-synthetic | `tests/test_ocr_eval.py` + `test_prime_offline_cache.py` | 字段 ≥98%（合成） |
| redline-gate | `tests/test_w2_gate.py` | 红线违规 0 |
| offline-e2e | `tests/test_e2e_home.py` + `test_home_summary.py` + `test_offline_provider.py` | 断网全链路绿 |
| real-smoke | `pytest -m real_api tests/test_real_smoke.py ...` | 真实模型协议+护栏成立 |

## 1. 赛前 T-1（联网，一次性预跑）

1. 确认 `.env` 就位（`MEDASSIST_LLM_BASE_URL/API_KEY`、`RAREGUARD_OCR_MODEL=Qwen/Qwen3.5-27B`），密钥绝不入库。
2. 预跑 OCR 缓存 + 生成演示化验单：
   ```bash
   python scripts/prime_offline_cache.py
   ```
   成功后本地生成 `data/demo/lab_report.png` 与 `data/ocr_cache/<sha>.json`（均 gitignored）。记下 `committed` 应为 3。
3. `python scripts/run_all_gates.py` 确认含 real-smoke 全绿。
4. 重置演示库（可选，浏览器手测会写入脏数据）：`python -m synth.generate_dataset`。

## 2. 现场断网演示（拔网 / 关 Wi-Fi）

```bash
RAREGUARD_OFFLINE=1 python -m rareguard.api.home_server
# 浏览器打开 http://127.0.0.1:8000   （本机回环，非外网）
```

四屏走一遍（约 8 分钟）：
1. **仪表盘**：填患儿编号 → 建档 → 看红绿灯 + 90 天趋势曲线。
2. **拍照录入**：上传 `data/demo/lab_report.png` → **命中 OCR 缓存**、双通道一致 → 三项直接入库（铁蛋白 1200 / 血小板 80 / 纤维蛋白原 1.2）。
3. **每日打卡**：连续 3 天高热（≥38.5）+ 症状 → 风险分爬升。
4. **预警详情**：转红 → 强弹窗 + 急诊准备清单 → 点「生成就诊一页纸（可打印带给医生）」→ 新标签页趋势/异常表/免责声明齐全 → Ctrl+P 打印。

演示话术锚点：「断网了，预警照样出——因为风险分 100% 来自规则引擎，AI 只负责把结论翻译成家长看得懂的话。」

收尾与答辩话术（共创 + 合规）见 `docs/roadshow-storyboard.md` §收尾与孵化；展开依据见 `docs/patient-cocreation-interview-guide.md`、`docs/compliance-deployment-onepager.md`。

## 3. 回退预案（现场故障处置）

| 现象 | 处置 |
|---|---|
| OCR 缓存 miss（换了图/删了缓存） | 拍照录入屏自动转手工录入：铁蛋白 1200 ng/mL、血小板 80 ×10⁹/L、纤维蛋白原 1.2 g/L 三项手动录 |
| 叙述文案不像话/被 L4 拦截 | 自动回退确定性模板（`source=template`），预警照常出，不影响演示 |
| 魔搭限流/密钥失效 | 全程 `RAREGUARD_OFFLINE=1`，不依赖任何外部服务 |
| 端口 8000 被占用（连不上/无响应） | 换端口起：`python -m uvicorn rareguard.api.home_server:create_served_app --factory --host 127.0.0.1 --port 8010`，浏览器开 `http://127.0.0.1:8010`；`netstat -ano \| grep :8000` 查占用 |
| 页面空白 | `node --check` 抽出的 `<script>` 排错；确认未改内联 SVG 模板字符串 |

## 4. 真实脱敏样例到位后（可选，赛后迭代）

样例（`.png` + 同名人工 `.json`）放本地 `data/real_samples/`（gitignored），跑：
```bash
python -m evals.real_ocr_eval
```
`mean_accuracy >= 0.95` 即达 spec §5 OCR 门禁；缺样例/缺密钥自动 skip 不报错。

## 5. 患者共创迭代记录（现场用）

访谈与可用性走查方法见 `docs/patient-cocreation-interview-guide.md`（招募/知情同意/问题清单/记录模板）。路演后收集 SJA 家长/风湿科医师反馈 → 规则取值调整须在 `docs/references.md` 登记文献出处 → 重跑 `run_all_gates.py` 确认指标不回退。

## 6. 赛前待办（人推动项 + 时间盒，今天 2026-09-22 → 路演 10-15）

> 只有两件事卡在你这边：**约到人**、**拿到真实脱敏样例**。其余我能自动做。owner：你=外联/线下，我=脚本/回填。

- [ ] **P0 启动（09-22 ~ 09-25）**
  - [ ] 你：联系 SJA 守护星星联盟 / 病痛挑战基金会，说明"共创访谈 + 3–5 份脱敏化验单"两项需求。
  - [ ] 我：知情同意书模板、样例标注模板（见附录 A/B）已备好，可直接转发。
- [ ] **P1 约人 + 拿样例（09-26 ~ 10-02）**
  - [ ] 你：约齐 4 位家长 + 2 位风湿科医生的档期（线上 30–40 分钟即可）。
  - [ ] 你：拿到样例后放本地 `data/real_samples/`（`.png` + 同名 `.json` 真值，**不入库**）。
  - [ ] 我：样例一到位即跑 `python -m evals.real_ocr_eval`，出 OCR 字段准确率报告。
- [ ] **P2 共创执行 + 迭代（10-03 ~ 10-09）**
  - [ ] 你：按提纲做访谈与四屏可用性走查（可录屏）。
  - [ ] 我：汇总反馈表 → 把 P0/P1 意见落到文案/打卡项/阈值，`references.md` 登记取值出处 → 重跑门禁确保不回退。
- [ ] **P3 回填真实数字（10-10 ~ 10-13）**
  - [ ] 我：把访谈人数、真实样例 OCR 准确率回填 `docs/roadshow-storyboard.md` 的 `__` 占位，更新 README 证据段。
  - [ ] 我：跑含 real-smoke 的 `run_all_gates.py` 全绿。
- [ ] **T-1（10-14）**：联网预跑 + 断网四屏走查（本手册 §1–§2）。
- [ ] **现场（10-15 ~ 10-17）**：演示 + 用 §收尾话术答"共创/合规"两问。

**降级底线**：若 P1 样例或 P2 访谈未及完成——路演用进行时表述（"联盟转介中、访谈提纲与知情同意已就绪"），技术硬核赛道不受影响，切勿谎报已完成。

### 附录 A：真实样例标注模板（`data/real_samples/xxx.json`，与同名 `.png` 配对）
```json
[
  {"code": "ferritin", "name": "血清铁蛋白", "value": 1200, "unit": "ng/mL", "ref_low": 15, "ref_high": 150},
  {"code": "plt", "name": "血小板计数", "value": 80, "unit": "10^9/L", "ref_low": 125, "ref_high": 350},
  {"code": "fib", "name": "纤维蛋白原", "value": 1.2, "unit": "g/L", "ref_low": 2, "ref_high": 4}
]
```
`code` 用归一码（ferritin/plt/fib/alt/tg/esr/crp），`value/unit/ref_low/ref_high` 按报告单**真实值**人工登记；评测按 `code`（或 `name`）对齐、数值容差 0.01。

### 附录 B：知情同意要点（访谈/样例共用，一页）
1. 目的：用于 RareGuard（开源，Apache-2.0）产品改进与准确率评测，不用于诊疗、不对外诊断。
2. 数据：化验单**先脱敏**（隐去姓名/住院号/身份证号等），仅本地留存，不进公开仓库；可随时要求删除。
3. 参与：访谈可录音/录屏仅用于内部改进；**可随时退出**，不影响任何医疗服务。
4. 免责：访谈者不提供医疗建议，一切病情判断"以主诊医生为准"。
5. 监护人签署（未成年人），签署人/日期留痕。
