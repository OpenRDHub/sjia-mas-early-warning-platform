"""断网演示包预跑：在线解析固定合成化验单一次并落 OCR 缓存。

现场演示（零网络）：
  1. 赛前联网跑一次  python scripts/prime_offline_cache.py
  2. 断网起服务      RAREGUARD_OFFLINE=1 python -m rareguard.api.home_server
  3. 拍照录入屏上传  data/demo/lab_report.png → 命中缓存、双通道一致、直接入库
"""
import base64
import io
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_DEMO_ROWS = [
    "Serum Ferritin      1200   ng/mL    (15 - 150)   H",
    "Platelet Count        80   10^9/L   (125 - 350)  L",
    "Fibrinogen           1.2   g/L      (2.0 - 4.0)  L",
]


def demo_lab_png_b64(save_path=None) -> str:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (640, 300), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 15), "RAREGUARD SYNTHETIC LAB REPORT", fill="black")
    y = 60
    for row in _DEMO_ROWS:
        d.text((20, y), row, fill="black")
        y += 40
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw = buf.getvalue()
    if save_path is not None:
        p = Path(save_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
    return base64.b64encode(raw).decode()


def prime_ocr_cache(image_b64: str, inner, cache_dir) -> list:
    from rareguard.ingest.ocr import parse_lab_report
    from rareguard.llm.offline_provider import RecordingOCR

    return parse_lab_report(image_b64, RecordingOCR(inner, cache_dir))


if __name__ == "__main__":
    from rareguard.ingest.ocr import parse_dual
    from rareguard.llm.offline_provider import CachedOCR, DEFAULT_CACHE_DIR
    from rareguard.llm.openai_compat_provider import (
        OpenAICompatProvider, is_configured, load_dotenv)

    load_dotenv()
    if not is_configured():
        print(json.dumps({"skipped": "未配置 MEDASSIST_LLM_*，无法在线预跑"},
                         ensure_ascii=False))
        sys.exit(2)
    provider = OpenAICompatProvider(
        os.environ["MEDASSIST_LLM_BASE_URL"],
        os.environ["MEDASSIST_LLM_API_KEY"],
        os.environ.get("RAREGUARD_OCR_MODEL")
        or os.environ["MEDASSIST_LLM_MODEL"],
    )
    png = Path("data") / "demo" / "lab_report.png"
    b64 = demo_lab_png_b64(png)
    prime_ocr_cache(b64, provider, DEFAULT_CACHE_DIR)
    offline = parse_dual(b64, CachedOCR())
    committed = sum(1 for i in offline if not i["needs_review"] and i["code"])
    print(json.dumps({"cache_dir": str(DEFAULT_CACHE_DIR),
                      "png": str(png), "committed": committed},
                     ensure_ascii=False))
