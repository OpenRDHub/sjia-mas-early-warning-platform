from evals.ocr_eval import score_ocr


def _item(code, value, unit="ng/mL", ref_low=15.0, ref_high=150.0,
          needs_review=False, name=None):
    return {"name": name or code, "code": code, "value": value,
            "unit": unit, "ref_low": ref_low, "ref_high": ref_high,
            "needs_review": needs_review}


def test_all_match():
    labeled = [_item("ferritin", 1200)]
    parsed = [_item("ferritin", 1200)]
    assert score_ocr(parsed, labeled) == {
        "total": 4, "matched": 4, "accuracy": 1.0}


def test_one_field_wrong():
    labeled = [_item("ferritin", 1200)]
    parsed = [_item("ferritin", 1000)]
    r = score_ocr(parsed, labeled)
    assert r["total"] == 4 and r["matched"] == 3 and r["accuracy"] == 0.75


def test_need_review_counts_unmatched():
    # 2 条真值 ×4 字段=8；needs_review 条目整条不计匹配 → 4/8
    labeled = [_item("ferritin", 1200), _item("crp", 40, unit="mg/L")]
    parsed = [_item("ferritin", 1200),
              _item("crp", 40, unit="mg/L", needs_review=True)]
    r = score_ocr(parsed, labeled)
    assert r == {"total": 8, "matched": 4, "accuracy": 0.5}


def test_missing_item_counts_unmatched():
    labeled = [_item("ferritin", 1200), _item("plt", 80, unit="10^9/L",
                                              ref_low=125, ref_high=350)]
    parsed = [_item("ferritin", 1200)]
    r = score_ocr(parsed, labeled)
    assert r["total"] == 8 and r["matched"] == 4


def test_empty_labeled():
    assert score_ocr([], []) == {"total": 0, "matched": 0, "accuracy": 1.0}
