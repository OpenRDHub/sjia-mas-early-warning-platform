from rareguard.verification.medical_guard import FALLBACK_TEXT, check_output


def test_diagnosis_statement_is_replaced_with_fallback():
    g = check_output("根据您的症状，您得了急性支气管炎。")
    assert not g.ok
    assert g.text == FALLBACK_TEXT
    assert "确诊" in g.reason
    assert g.needs_review


def test_explicit_diagnosis_conclusion_is_blocked():
    g = check_output("结合检查结果，确诊为社区获得性肺炎。")
    assert not g.ok
    assert g.needs_review


def test_prescription_suggestion_is_blocked():
    g = check_output("建议服用阿莫西林胶囊 500mg 每日三次。")
    assert not g.ok
    assert g.text == FALLBACK_TEXT


def test_dosage_recommendation_is_blocked():
    g = check_output("每次一片，每日两次，连续服用一周。")
    assert not g.ok
    assert "剂量" in g.reason


def test_normal_soap_draft_passes():
    text = "现病史：患者三天前无明显诱因出现胸痛，伴咳嗽，无发热。既往高血压病史五年，青霉素过敏。"
    g = check_output(text)
    assert g.ok
    assert g.text == text
    assert not g.needs_review


def test_neutral_medication_reference_passes():
    g = check_output("提示：患者正在服用的药物与本次症状可能存在关联，请医生复核用药情况。")
    assert g.ok


def test_vital_signs_with_units_do_not_trigger_dosage():
    g = check_output("患者血压 152/95 mmHg，体温 38.5 度，血糖 5.6 mmol/L，体重 70kg。")
    assert g.ok


def test_fallback_text_itself_is_compliant():
    assert check_output(FALLBACK_TEXT).ok
