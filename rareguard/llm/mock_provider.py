"""Mock LLM Provider：基于确定性规则的脚本化应答，用于开发与评测。

按 system 提示词中的节点标记路由：
- N1 采集：从患者文本抽取槽位关键词，返回 JSON（slots/next_question/collecting_done）
- N5 成文：按槽位与 EHR 上下文拼装 SOAP 草稿模板，A/P 留给医生
协议与真实 LLM 完全一致（prompt 即协议），保证换模型不改护栏。
"""

import json
import re

from rareguard.llm.provider import BaseLLMProvider, LLMResponse

_SYMPTOM_KWS = (
    "胸痛", "胸口疼", "胸口疼痛", "心前区痛", "头痛", "头疼", "咳嗽",
    "发热", "发烧", "呕吐", "腹泻", "皮疹", "头晕", "心慌", "气短", "乏力",
)
_DURATION_RE = re.compile(
    r"[一两二三四五六七八九十\d]+\s*个?\s*(?:小时|天|日|星期|周|月|年|分钟)"
)
_SEVERITY_KWS = ("轻微", "有点", "中等", "严重", "剧烈", "难以忍受")
_ASSOC_KWS = (
    "出汗", "冷汗", "大汗", "恶心", "发热", "头晕", "乏力", "心慌", "气短", "呕吐",
)


class MockLLMProvider(BaseLLMProvider):
    name = "mock"

    def chat(self, messages, tools=None) -> LLMResponse:
        system = messages[0]["content"] if messages else ""
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        if "N5" in system:
            return LLMResponse(text=self._draft(last_user), model=self.name)
        return LLMResponse(text=self._collect(last_user), model=self.name)

    # ---- N1 采集：规则抽槽 + 下一问 ----

    def _collect(self, user_json: str) -> str:
        try:
            payload = json.loads(user_json)
            text, known = payload.get("text", ""), dict(payload.get("known_slots", {}))
        except json.JSONDecodeError:
            text, known = user_json, {}
        merged = {**known, **self._extract(text)}
        done = bool(merged.get("chief_complaint") and merged.get("duration"))
        if done:
            question = "预问诊信息已记录，感谢配合。"
        elif not merged.get("chief_complaint"):
            question = "请问您最主要的不适是什么？"
        elif not merged.get("duration"):
            question = "这种情况持续多久了？"
        elif not merged.get("severity"):
            question = "不适的程度如何？轻微、中等还是剧烈？"
        else:
            question = "有没有其他伴随症状？比如出汗、恶心、发热等。"
        return json.dumps(
            {"slots": merged, "next_question": question, "collecting_done": done},
            ensure_ascii=False,
        )

    @staticmethod
    def _extract(text: str) -> dict:
        slots: dict = {}
        for kw in _SYMPTOM_KWS:
            if kw in text:
                slots["chief_complaint"] = kw
                break
        m = _DURATION_RE.search(text)
        if m:
            slots["duration"] = m.group().replace(" ", "")
        for kw in _SEVERITY_KWS:
            if kw in text:
                slots["severity"] = kw
                break
        assoc = [
            kw for kw in _ASSOC_KWS
            if kw in text and kw != slots.get("chief_complaint")
        ]
        if assoc:
            slots["associated"] = "、".join(assoc)
        return slots

    # ---- N5 成文：SOAP 模板，A/P 100% 留给医生（R1 红线） ----

    @staticmethod
    def _draft(user_json: str) -> str:
        try:
            payload = json.loads(user_json)
            slots, ehr = payload.get("slots", {}), payload.get("ehr", "")
        except json.JSONDecodeError:
            slots, ehr = {}, ""
        pending = "—（待医生补充）"
        g = lambda k: slots.get(k, pending)  # noqa: E731
        return (
            "【SOAP 病历草稿 | AI 辅助参考，需医生确认】\n"
            f"S（主观）：主诉：{g('chief_complaint')}；持续：{g('duration')}；"
            f"程度：{g('severity')}；伴随：{g('associated')}\n"
            f"O（客观）：{ehr or '（无 EHR 记录）'}\n"
            "A（评估）：【待医生补充】\n"
            "P（处理）：【待医生补充】"
        )
