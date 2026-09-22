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
