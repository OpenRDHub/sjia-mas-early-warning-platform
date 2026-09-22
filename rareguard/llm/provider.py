"""LLM 可插拔 Provider 统一接口（§3.2）。

所有模型切换必须通过 §7 评测回归后才可上线；
提示词、校验规则与模型解耦——换模型不改护栏。
"""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


def extract_json(text: str) -> dict:
    """从 LLM 输出鲁棒提取 JSON 对象（容忍 markdown 代码块/前后缀文字）。

    所有编排节点解析 LLM 协议输出必须经此函数，禁止裸 json.loads——
    真实模型（如 MiMo）常以 ```json 代码块包裹返回。
    """
    m = re.search(r"\{.*\}", text.strip(), re.DOTALL)
    if not m:
        raise ValueError(f"LLM 输出中未找到 JSON: {text[:200]}")
    return json.loads(m.group())


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str = ""
    usage: dict = field(default_factory=dict)  # token 用量，供 §6.4 成本统计


class BaseLLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def chat(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> LLMResponse:
        """统一对话接口：messages=[{role, content}]；tools 为可选工具定义。"""
