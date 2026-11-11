"""离线降级 Provider：OCR 预跑缓存 + 叙述失败回退（spec §2 降级路径 / §6 网络风险）。

在线跑一次 RecordingOCR 落盘缓存；断网演示用 CachedOCR 命中同图结果，
未命中即抛错 → API 层降级为手工录入；OfflineNarrate 必失败 → narrate
回退确定性模板。护栏与规则引擎不感知 Provider 差异。
"""
import hashlib
import json
from pathlib import Path

from rareguard.llm.provider import BaseLLMProvider, LLMResponse

DEFAULT_CACHE_DIR = Path("data") / "ocr_cache"


def _image_key(messages) -> str:
    for m in messages:
        content = m.get("content")
        if isinstance(content, list):
            for part in content:
                if part.get("type") == "image_url":
                    url = part["image_url"]["url"]
                    return hashlib.sha256(url.encode()).hexdigest()
    raise RuntimeError("消息中未找到图片")


class CachedOCR(BaseLLMProvider):
    name = "cached-ocr"

    def __init__(self, cache_dir: str | Path | None = None):
        self.cache_dir = Path(cache_dir or DEFAULT_CACHE_DIR)

    def chat(self, messages, tools=None):
        f = self.cache_dir / f"{_image_key(messages)}.json"
        if not f.exists():
            raise RuntimeError(f"ocr cache miss: {f.name}")
        return LLMResponse(text=f.read_text(encoding="utf-8"),
                           model=self.name)


class RecordingOCR(BaseLLMProvider):
    """透传 inner 并把响应文本写入缓存，供离线演示复用。"""

    name = "recording-ocr"

    def __init__(self, inner: BaseLLMProvider,
                 cache_dir: str | Path | None = None):
        self.inner = inner
        self.cache_dir = Path(cache_dir or DEFAULT_CACHE_DIR)

    def chat(self, messages, tools=None):
        resp = self.inner.chat(messages, tools)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        f = self.cache_dir / f"{_image_key(messages)}.json"
        f.write_text(resp.text, encoding="utf-8")
        return resp


class OfflineNarrate(BaseLLMProvider):
    name = "offline-narrate"

    def chat(self, messages, tools=None):
        raise RuntimeError("offline mode: 叙述层回退确定性模板")


def build_providers(offline: bool) -> tuple[BaseLLMProvider, BaseLLMProvider]:
    """返回 (ocr_provider, narrate_provider)。"""
    if offline:
        return CachedOCR(), OfflineNarrate()
    import os

    from rareguard.llm.openai_compat_provider import (OpenAICompatProvider,
                                                      load_dotenv)

    load_dotenv()
    base = os.environ.get("MEDASSIST_LLM_BASE_URL")
    key = os.environ.get("MEDASSIST_LLM_API_KEY")
    ocr = OpenAICompatProvider(
        base, key, os.environ.get("RAREGUARD_OCR_MODEL")
        or os.environ.get("MEDASSIST_LLM_MODEL"))
    narrate = OpenAICompatProvider(
        base, key, os.environ.get("RAREGUARD_NARRATE_MODEL")
        or os.environ.get("MEDASSIST_LLM_MODEL"))
    return ocr, narrate
