"""L3 事实接地测试：数值断言出处校验（幻觉剂量防线）+ 管道集成。"""

import pytest

from rareguard.verification.fact_check import check_grounded, extract_claims
from rareguard.verification.pipeline import run_verification_pipeline


class TestExtractClaims:
    def test_extracts_numeric_units(self):
        assert set(extract_claims("10mg 每日一次，共 7 天")) == {
            "10mg", "7 天", "一次",
        }

    def test_extracts_chinese_numerals(self):
        assert extract_claims("疼了三天") == ["三天"]

    def test_no_claims_in_plain_text(self):
        assert extract_claims("胸口疼痛，既往高血压病史") == []


class TestCheckGrounded:
    def test_clean_when_all_grounded(self):
        ctx = "血压 150/95 mmHg；氯雷他定片；3天"
        r = check_grounded("血压 150/95mmHg，皮疹 3 天", ctx)
        assert r.ok and not r.needs_review  # 空格归一化匹配

    def test_hallucinated_dose_flagged(self):
        """真实案例：EHR 只有药名，模型编造剂量 → 标记人工复核。"""
        ctx = "当前用药：氯雷他定片"
        r = check_grounded("当前用药：氯雷他定片 10mg 每日一次", ctx)
        assert not r.ok and r.needs_review
        assert "10mg" in r.ungrounded

    def test_patient_narration_grounded_via_slots(self):
        ctx = '{"slots": {"duration": "三天"}}'
        assert check_grounded("疼痛三天", ctx).ok

    def test_empty_draft_or_context(self):
        assert check_grounded("", "").ok
        # 空上下文（无 EHR）下任何数值断言都是未接地
        r = check_grounded("血压 150mmHg", "")
        assert not r.ok and "150mmHg" in r.ungrounded


class TestPipelineIntegration:
    def test_ungrounded_marks_needs_review_but_not_blocked(self, tmp_path):
        """L3 未接地：文本不替换、不阻断，needs_review=True。"""
        pr = run_verification_pipeline(
            user_input="我身上起了皮疹",
            llm_output="当前用药：氯雷他定片 10mg 每日一次",
            trace_id="t-l3-1",
            audit_path=tmp_path / "a.jsonl",
            fact_context='{"slots": {}, "ehr": "当前用药：氯雷他定片"}',
        )
        assert pr.ok  # 不阻断
        assert pr.needs_review  # 标记人工
        assert "L3" in pr.layers and pr.layers["L3"]["ungrounded"]

    def test_grounded_clean(self, tmp_path):
        pr = run_verification_pipeline(
            user_input="我胸口疼",
            llm_output="患者胸口疼三天，青霉素过敏史",
            trace_id="t-l3-2",
            audit_path=tmp_path / "a.jsonl",
            fact_context='{"slots": {"duration": "三天"}, "ehr": "过敏史：青霉素"}',
        )
        assert pr.ok and not pr.needs_review

    def test_existing_l4_behavior_unchanged(self, tmp_path):
        """L4 替换照常（L3/L4 独立工作）。"""
        pr = run_verification_pipeline(
            user_input="我胸口疼",
            llm_output="建议服用氯雷他定片 10mg 每日一次",
            trace_id="t-l3-3",
            audit_path=tmp_path / "a.jsonl",
            fact_context='{"ehr": "氯雷他定片"}',
        )
        assert pr.ok and pr.needs_review
        assert "拦截" in pr.text  # L4 替换为兜底文案
