"""家庭叙述层：LLM 仅把规则结论翻译为家长可读表达，输出强制过六层管道。

任何失败路径都回退到确定性模板（fail-safe 到模板，绝不 fail-open 到模型原文）。
"""
import json

from rareguard.verification.pipeline import run_verification_pipeline

NARRATE_SYSTEM = "N9 家庭叙述"

_DISCLAIMER = "AI 辅助参考，请以医生诊断为准。"

# 免责声明由渲染层追加，绝不让模型生成——否则 L4 护栏会把
# "以医生诊断为准"误判为确诊句式（见基座 R3：护栏与模型解耦）。
_SYSTEM_PROMPT = (
    f"{NARRATE_SYSTEM}\n你是面向患儿家长的解读助手。输入是规则引擎给出的"
    "结构化风险结论，你只能基于其中的事实转述，禁止下诊断、禁止提及药物"
    "与剂量、禁止预测后果制造恐慌。不要输出免责声明，系统会自动追加。"
)


def build_prompt(assessment) -> str:
    return json.dumps({
        "level": assessment.level,
        "score": assessment.score,
        "hits": [{"rule_id": h.rule_id, "name": h.name,
                  "level": h.level, "evidence": h.evidence}
                 for h in assessment.hits],
    }, ensure_ascii=False)


def template_text(assessment) -> str:
    if assessment.level == "red":
        head = (f"检测到高危指标变化（风险评分 {assessment.score}）。"
                "建议24小时内携带本报告与近期化验单就诊或急诊。")
    elif assessment.level == "yellow":
        head = (f"指标出现需关注的趋势（风险评分 {assessment.score}）。"
                "建议48小时内安排复诊，并继续每日打卡与按医嘱复查。")
    else:
        head = "各项指标平稳，继续观察，按医嘱定期复查即可。"
    names = "、".join(dict.fromkeys(h.name for h in assessment.hits))
    if names:
        head += f" 触发提示：{names}。"
    return f"{head}{_DISCLAIMER}"


def narrate(assessment, provider, trace_id: str = "") -> tuple:
    evidence = build_prompt(assessment)
    try:
        resp = provider.chat([
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": evidence},
        ])
    except Exception:
        return template_text(assessment), {"source": "template", "ok": True}
    result = run_verification_pipeline(
        evidence, resp.text, trace_id, fact_context=evidence)
    if not result.ok:
        return template_text(assessment), {"source": "blocked", "ok": True}
    text = result.text
    if _DISCLAIMER not in text:
        text = f"{text}{_DISCLAIMER}"
    return text, {"source": "llm", "ok": True}
