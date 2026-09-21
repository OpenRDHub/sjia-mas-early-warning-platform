"""一键全门禁编排（彩排/发布前自检，spec §5 五道门禁）。

用法：python scripts/run_all_gates.py     # 真跑子进程，任一 fail 退出码 1
仅核对计划表：见 GATE_STEPS。real-smoke 需魔搭密钥，未配置则记 skip。
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

GATE_STEPS = [
    {"label": "w1-metrics", "requires_net": False,
     "argv": [sys.executable, "-m", "pytest",
              "tests/test_gate_rareguard.py", "-q"]},
    {"label": "ocr-synthetic", "requires_net": False,
     "argv": [sys.executable, "-m", "pytest",
              "tests/test_ocr_eval.py", "tests/test_prime_offline_cache.py",
              "-q"]},
    {"label": "redline-gate", "requires_net": False,
     "argv": [sys.executable, "-m", "pytest", "tests/test_w2_gate.py", "-q"]},
    {"label": "offline-e2e", "requires_net": False,
     "argv": [sys.executable, "-m", "pytest",
              "tests/test_e2e_home.py", "tests/test_home_summary.py",
              "tests/test_offline_provider.py", "-q"]},
    {"label": "real-smoke", "requires_net": True,
     "argv": [sys.executable, "-m", "pytest", "-m", "real_api",
              "tests/test_real_smoke.py", "tests/test_real_provider_smoke.py",
              "-q"]},
]


def run_all():
    from rareguard.llm.openai_compat_provider import (
        is_configured, load_dotenv)

    load_dotenv()
    results = {}
    for step in GATE_STEPS:
        if step["label"] == "real-smoke" and not is_configured():
            results[step["label"]] = "skip"
            continue
        proc = subprocess.run(step["argv"])
        results[step["label"]] = "pass" if proc.returncode == 0 else "fail"
    return results


if __name__ == "__main__":
    r = run_all()
    print(json.dumps(r, ensure_ascii=False, indent=2))
    sys.exit(1 if "fail" in r.values() else 0)
