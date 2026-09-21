"""OpenAI 兼容协议的真实 LLM Provider（书生/商汤/云知声等国内平台均兼容）。

密钥通过环境变量或项目根 .env 提供，绝不写入代码库（.env 已入 .gitignore）：
  MEDASSIST_LLM_BASE_URL / MEDASSIST_LLM_API_KEY / MEDASSIST_LLM_MODEL

开发/评测期使用云端 API + Mock 脱敏数据；正式部署按 §6.2 换私有化端点——
Provider 不变仅换配置，这是 §3.2"换模型不改护栏"的落地。
"""

import os
import time
from pathlib import Path

import requests

from rareguard.llm.provider import BaseLLMProvider, LLMResponse, extract_json

__all__ = ["OpenAICompatProvider", "extract_json", "load_dotenv", "is_configured"]

_ENV_KEYS = (
    "MEDASSIST_LLM_BASE_URL",
    "MEDASSIST_LLM_API_KEY",
    "MEDASSIST_LLM_MODEL",
)


def load_dotenv() -> None:
    """把项目根 .env 的 KEY=VALUE 注入环境（不覆盖已有值）。"""
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def is_configured() -> bool:
    """三项配置是否齐备（未配置时冒烟评测自动跳过）。"""
    load_dotenv()
    return all(os.environ.get(k) for k in _ENV_KEYS)


class OpenAICompatProvider(BaseLLMProvider):
    name = "openai-compat"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
        temperature: float = 0.0,
    ) -> None:
        load_dotenv()
        self.base_url = (
            base_url or os.environ.get(_ENV_KEYS[0]) or ""
        ).rstrip("/")
        self.api_key = api_key or os.environ.get(_ENV_KEYS[1]) or ""
        self.model = model or os.environ.get(_ENV_KEYS[2]) or ""
        if not (self.base_url and self.api_key and self.model):
            raise RuntimeError(
                f"LLM 配置不完整，请设置 {'/'.join(_ENV_KEYS)}（环境变量或项目根 .env）"
            )
        self.timeout = timeout
        # 评测要求确定性输出，默认 temperature=0
        self.temperature = temperature

    def chat(self, messages, tools=None) -> LLMResponse:
        """对话补全；429 限流时指数退避重试（最多 3 次：20s/40s）。"""
        for attempt in range(3):
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature,
                },
                timeout=self.timeout,
            )
            if resp.status_code == 429 and attempt < 2:
                time.sleep(20 * (attempt + 1))
                continue
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]["message"]
            usage = {
                k: v for k, v in data.get("usage", {}).items()
                if isinstance(v, (int, float))
            }
            return LLMResponse(
                text=choice["content"],
                model=data.get("model", self.model),
                usage=usage,
            )
        raise RuntimeError("unreachable")
