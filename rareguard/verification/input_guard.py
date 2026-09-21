"""L1 输入净化：提示注入模式库（中英）+ 角色覆盖检测 + 超长截断。

命中注入/角色覆盖即拒绝该轮输入（ok=False，不返回文本）；
正常文本放行，超长输入截断到 MAX_INPUT_CHARS。
"""

from dataclasses import dataclass

MAX_INPUT_CHARS = 4000

# 中文提示注入句式
_CN_PATTERNS: tuple[str, ...] = (
    "忽略以上", "忽略之前", "忽略上述", "忽略所有", "忽略前面",
    "无视以上", "无视之前", "无视所有",
    "不受限制", "没有任何限制", "解除限制", "绕过限制",
    "越狱", "开发者模式", "开发者指令",
    "你现在是一个", "你现在是", "从现在起你", "假装你是",
    "打印你的系统提示", "显示你的提示词", "泄露你的提示", "复述你的指令",
)

# 英文提示注入句式（匹配前统一转小写）
_EN_PATTERNS: tuple[str, ...] = (
    "ignore previous", "ignore all", "ignore above", "ignore prior",
    "disregard previous", "disregard all", "disregard above",
    "do anything now", "act as dan", "dan mode",
    "you are now", "pretend to be", "act as if",
    "developer mode", "jailbreak",
    "print your system prompt", "reveal your prompt", "show your instructions",
)

# 角色覆盖标记（小写匹配）
_ROLE_MARKERS: tuple[str, ...] = (
    "system:", "[system]", "<|im_start|>", "<|im_end|>",
    "### instruction", "### system", "### assistant", "role: system",
)


@dataclass(frozen=True)
class InputCheckResult:
    ok: bool
    text: str
    reason: str = ""


def check_input(text: str) -> InputCheckResult:
    """净化单轮患者输入；任何命中即拒绝该轮并给出原因。"""
    for pattern in _CN_PATTERNS:
        if pattern in text:
            return InputCheckResult(
                ok=False, text="", reason=f"疑似提示注入（命中模式: {pattern}）"
            )
    lowered = text.lower()
    for pattern in _EN_PATTERNS:
        if pattern in lowered:
            return InputCheckResult(
                ok=False, text="", reason=f"疑似提示注入（命中模式: {pattern}）"
            )
    for marker in _ROLE_MARKERS:
        if marker in lowered:
            return InputCheckResult(
                ok=False, text="", reason=f"疑似角色覆盖（命中标记: {marker}）"
            )
    if len(text) > MAX_INPUT_CHARS:
        text = text[:MAX_INPUT_CHARS]
    return InputCheckResult(ok=True, text=text)
