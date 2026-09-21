import pytest
from rareguard.analysis.normalize import (
    normalize, UnknownIndicator, UnitConversionError)


def test_chinese_alias():
    assert normalize("血清铁蛋白", 620, "ng/mL") == ("ferritin", 620.0)
    assert normalize("C反应蛋白", 3.2, "mg/dL") == ("crp", 32.0)


def test_unit_equivalence():
    assert normalize("铁蛋白", 620, "μg/L") == ("ferritin", 620.0)


def test_fib_mgl_to_gl():
    assert normalize("纤维蛋白原", 1200, "mg/L") == ("fib", 1.2)


def test_tg_mgdl_to_mmol():
    code, v = normalize("甘油三酯", 266, "mg/dL")
    assert code == "tg" and abs(v - 3.0) < 0.01


def test_temp_f_to_c():
    code, v = normalize("体温", 101.3, "°F")
    assert code == "temp" and abs(v - 38.5) < 0.01


def test_errors():
    with pytest.raises(UnknownIndicator):
        normalize("血糖", 5, "mmol/L")
    with pytest.raises(UnitConversionError):
        normalize("铁蛋白", 5, "g/dL")
