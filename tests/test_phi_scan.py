from rareguard.verification.phi_scan import scan_phi


def test_id_card_leak_blocks():
    s = scan_phi("患者身份证号 330102199001011234 已登记。")
    assert not s.ok
    assert s.id_card_hits == 1
    assert "身份证" in s.reason


def test_phone_number_warns_but_passes():
    s = scan_phi("家属联系电话 13812345678，请回访。")
    assert s.ok
    assert s.phone_hits == 1


def test_normal_clinical_text_is_clean():
    s = scan_phi("现病史：患者三天前出现胸痛，伴咳嗽，无发热。血压 152/95 mmHg。")
    assert s.ok
    assert s.id_card_hits == 0
    assert s.phone_hits == 0


def test_long_digit_string_does_not_false_positive():
    # 20 位病历长 ID：前后无边界隔离，不应被拆成手机号/身份证
    s = scan_phi("就诊流水号 3301021990010112345678 已生成。")
    assert s.id_card_hits == 0
    assert s.phone_hits == 0


def test_multiple_id_cards_all_counted():
    s = scan_phi("330102199001011234 与 110101198505152345 重复建档。")
    assert not s.ok
    assert s.id_card_hits == 2


def test_leaked_values_are_masked_in_reason():
    s = scan_phi("身份证号 330102199001011234 已登记。")
    assert "330102199001011234" not in s.reason
