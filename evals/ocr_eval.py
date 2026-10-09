"""OCR 字段级准确率评测（spec §5 门禁 ≥95%）。

labeled 为人工登记真值 JSON（格式同 parse_lab_report 输出），
data/real_samples/ 就绪后：python -m evals.ocr_eval parsed.json labeled.json
"""
import json
import sys

FIELDS = ("value", "unit", "ref_low", "ref_high")
_TOL = 0.01


def _eq(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= _TOL
    return a == b


def score_ocr(parsed: list[dict], labeled: list[dict]) -> dict:
    idx = {}
    for p in parsed:
        idx.setdefault(p.get("code") or p.get("name"), p)
    total = matched = 0
    for g in labeled:
        p = idx.get(g.get("code") or g.get("name"))
        usable = p is not None and not p.get("needs_review")
        for f in FIELDS:
            total += 1
            if usable and _eq(p.get(f), g.get(f)):
                matched += 1
    accuracy = matched / total if total else 1.0
    return {"total": total, "matched": matched, "accuracy": accuracy}


def main(argv: list[str]) -> int:
    parsed = json.loads(open(argv[1], encoding="utf-8").read())
    labeled = json.loads(open(argv[2], encoding="utf-8").read())
    r = score_ocr(parsed, labeled)
    print(json.dumps(r, ensure_ascii=False))
    return 0 if r["accuracy"] >= 0.95 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
