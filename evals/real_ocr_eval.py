"""真实脱敏样例 OCR 字段准确率评测（spec §3.2 / §5 ≥95%）。

样例放本地 data/real_samples/*.png（同名 .json 为人工真值 label），绝不入库。
缺样例或缺密钥 → skip 且不失败：python -m evals.real_ocr_eval
"""
import base64
import json
import sys
from pathlib import Path

from evals.ocr_eval import score_ocr
from rareguard.ingest.ocr import parse_lab_report

DEFAULT_DIR = Path("data") / "real_samples"


def evaluate_samples(samples_dir, provider):
    samples_dir = Path(samples_dir)
    pngs = sorted(samples_dir.glob("*.png")) if samples_dir.exists() else []
    if not pngs:
        return None
    per_file = []
    for png in pngs:
        label_path = png.with_suffix(".json")
        if not label_path.exists():
            continue
        label = json.loads(label_path.read_text(encoding="utf-8"))
        b64 = base64.b64encode(png.read_bytes()).decode()
        parsed = parse_lab_report(b64, provider)
        per_file.append({"file": png.name,
                         "accuracy": score_ocr(parsed, label)["accuracy"]})
    mean = (sum(f["accuracy"] for f in per_file) / len(per_file)
            if per_file else 0.0)
    return {"files": len(per_file), "per_file": per_file,
            "mean_accuracy": round(mean, 4)}


def main(argv):
    samples_dir = Path(argv[1]) if len(argv) > 1 else DEFAULT_DIR
    if not samples_dir.exists() or not list(samples_dir.glob("*.png")):
        print(json.dumps({"skipped": f"无真实样例：{samples_dir}"},
                         ensure_ascii=False))
        return 0
    from rareguard.llm.offline_provider import build_providers
    from rareguard.llm.openai_compat_provider import (
        is_configured, load_dotenv)

    load_dotenv()
    if not is_configured():
        print(json.dumps({"skipped": "未配置 MEDASSIST_LLM_*"},
                         ensure_ascii=False))
        return 0
    ocr, _ = build_providers(offline=False)
    r = evaluate_samples(samples_dir, ocr)
    print(json.dumps(r, ensure_ascii=False))
    return 0 if r and r["mean_accuracy"] >= 0.95 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
