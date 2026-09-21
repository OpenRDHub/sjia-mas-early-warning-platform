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

- 设计规格：`docs/superpowers/specs/2026-09-21-rareguard-t04-design.md`
- 实施计划：`docs/superpowers/plans/`
- 规则取值文献：`docs/references.md`

## 安全红线

不确诊、不给用药方案、所有 AI 输出强制"以医生诊断为准"标记；演示数据全部为合成数据。

## License

Apache-2.0
