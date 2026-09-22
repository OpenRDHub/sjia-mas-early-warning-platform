# 守望 · RareGuard

面向 SJA（全身型幼年特发性关节炎）患儿家庭的 **MAS（巨噬细胞激活综合征）并发症动态预警平台**。
「罕见·无界黑客松」赛题 04 参赛作品（2026.10.15–10.17 杭州）。

## 核心设计

风险结论 **100% 出自确定性规则引擎**（绝对阈值 + 趋势斜率 + MAS 八项评分），LLM 仅将规则结论翻译为家长能读懂的表达，不参与任何判断——系统断网照常出预警。

```
家属端 Web PWA（拍照录入 / 每日打卡 / 仪表盘 / 预警详情）
   ▼
FastAPI 网关（角色裁剪 + 审计）
   ▼
OCR 解析（Qwen-VL，双通道校验，W2）│ 打卡表单
   ▼
SQLite/PG 时序库（TimeSeriesProvider 只读抽象）
   ▼
规则引擎 R-A 阈值 / R-B 趋势 / R-C MAS 评分（不经 LLM）
   ▼
六层校验管道（复用医疗级验证架构）→ 红/黄/绿分级预警 + WORM 审计
```

## 开发复现

```bash
pip install -r requirements.txt
python -m pytest -q            # 全量单测 + 评测门禁（real_api 标记自动跳过）
python -m synth.generate_dataset  # 重新生成合成评测集（seed=42 可复现）
```

## 本地运行与演示

```bash
# 在线模式（.env 配置魔搭 OpenAI 兼容端点，密钥不入库）
python -m rareguard.api.home_server

# 断网演示模式：OCR 走预跑缓存，叙述回退确定性模板，规则引擎照常出分
RAREGUARD_OFFLINE=1 python -m rareguard.api.home_server

# 端到端演示脚本（零网络，输出建档→打卡→OCR→趋势→红色预警全链路 JSON）
python scripts/demo_e2e.py

# 播种近三日「绿→黄→红」合成高危样例，供彩排与截图取证（数据不入库）
python scripts/seed_demo_db.py data/demo/rareguard_demo.db
```

浏览器打开 `http://127.0.0.1:8000/` 即家庭端四屏 PWA（单文件、零外部依赖）。
带 `?pid=` 深链（如 `/?pid=PDEMO`）可自动选中患儿并直接呈现当前风险，便于分享与无头取证。

预警详情屏可「生成就诊一页纸」——`GET /api/home/summary/{pid}` 返回内联趋势图 + 异常化验表 + 命中规则的打印友好摘要，供家长带去急诊。

效果预览（由播种脚本 + 无头浏览器自动截取）：`docs/assets/01-red-alert.png`、`docs/assets/02-one-pager.png`。

## 彩排与发布门禁

```bash
# 赛前联网预跑一次：解析合成化验单并落 OCR 缓存（生成 data/demo/lab_report.png）
python scripts/prime_offline_cache.py

# 一键五道门禁（召回/OCR/红线/断网E2E/真实冒烟），任一 fail 退出码 1
python scripts/run_all_gates.py

# 真实脱敏样例到位后（本地 data/real_samples/，不入库）：字段准确率 ≥95%
python -m evals.real_ocr_eval
```

现场操作与回退预案见 `docs/rehearsal-checklist.md`，10 分钟路演分镜见 `docs/roadshow-storyboard.md`。

- 设计规格：`docs/superpowers/specs/2026-09-21-rareguard-t04-design.md`
- 实施计划：`docs/superpowers/plans/`
- 规则取值文献：`docs/references.md`

## 安全红线

不确诊、不给用药方案、所有 AI 输出强制"以医生诊断为准"标记；演示数据全部为合成数据。

## License

Apache-2.0
