"""最小验证管道：L1 输入净化 → L3 事实接地 → L4 医疗护栏 → L5 PHI 扫描，全程 L6 审计。

fail-closed 总原则：任一层崩溃或审计写入失败 → 阻断响应。
L4 命中不阻断：替换为兜底文案并标记人工复核（§5 L4 策略）。
L3 未接地不阻断：标记 needs_review 交医生复核（fail-safe）。
L2 权限隔离为 DB 物理层约束（P0b 落地），不在运行时管道内。
"""

from dataclasses import dataclass
from pathlib import Path

from rareguard.verification.audit import log_event
from rareguard.verification.fact_check import check_grounded
from rareguard.verification.input_guard import check_input
from rareguard.verification.medical_guard import check_output
from rareguard.verification.phi_scan import scan_phi

BLOCKED_TEXT = "本轮内容未通过安全校验，已终止。如有不适请直接咨询医生。"


@dataclass(frozen=True)
class PipelineResult:
    ok: bool
    text: str
    needs_review: bool
    trace_id: str
    layers: dict


def _finalize(
    ok: bool,
    text: str,
    needs_review: bool,
    trace_id: str,
    user_input: str,
    layers: dict,
    audit_path: Path | None,
) -> PipelineResult:
    try:
        log_event(
            {
                "event": "pipeline_verification",
                "trace_id": trace_id,
                "ok": ok,
                "needs_review": needs_review,
                "input": user_input,
                "final_output": text,
                "layers": layers,
            },
            path=audit_path,
        )
    except Exception:
        # L6 fail-closed：审计失败 = 阻断响应
        return PipelineResult(
            ok=False, text=BLOCKED_TEXT, needs_review=False,
            trace_id=trace_id, layers=layers,
        )
    return PipelineResult(
        ok=ok, text=text, needs_review=needs_review,
        trace_id=trace_id, layers=layers,
    )


def run_verification_pipeline(
    user_input: str,
    llm_output: str,
    trace_id: str,
    audit_path: Path | None = None,
    fact_context: str = "",
) -> PipelineResult:
    """LLM 输出返回任一终端前的强制校验管道（L1/L3/L4/L5 + L6 审计）。"""
    layers: dict = {}
    try:
        # L1 输入净化：拒绝该轮输入
        v1 = check_input(user_input)
        layers["L1"] = {"ok": v1.ok, "reason": v1.reason}
        if not v1.ok:
            return _finalize(
                False, BLOCKED_TEXT, False, trace_id, user_input, layers, audit_path
            )

        # L3 事实接地：未接地数值断言标记人工复核，不阻断
        v3 = check_grounded(llm_output, fact_context)
        layers["L3"] = {
            "ok": v3.ok,
            "ungrounded": list(v3.ungrounded),
            "needs_review": v3.needs_review,
        }

        # L4 医疗护栏：命中替换为兜底文案，不阻断
        v4 = check_output(llm_output)
        layers["L4"] = {
            "ok": v4.ok, "reason": v4.reason, "needs_review": v4.needs_review,
        }
        text = v4.text

        # L5 PHI 扫描：身份证级阻断，手机号警告
        v5 = scan_phi(text)
        layers["L5"] = {
            "ok": v5.ok,
            "id_card_hits": v5.id_card_hits,
            "phone_hits": v5.phone_hits,
            "reason": v5.reason,
        }
        if not v5.ok:
            return _finalize(
                False, BLOCKED_TEXT, False, trace_id, user_input, layers, audit_path
            )

        return _finalize(
            True, text, v4.needs_review or v3.needs_review,
            trace_id, user_input, layers, audit_path,
        )
    except Exception as exc:  # fail-closed：任一层崩溃即阻断
        layers["PIPELINE_ERROR"] = {"error": f"{type(exc).__name__}: {exc}"}
        return _finalize(
            False, BLOCKED_TEXT, False, trace_id, user_input, layers, audit_path
        )
