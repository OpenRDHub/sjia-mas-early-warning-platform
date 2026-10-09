from pathlib import Path

from rareguard.risk.rules import assess, load_default_rules


def test_default_rule_set_loads_and_is_wellformed():
    rules = load_default_rules()
    assert len(rules) >= 8
    for r in rules:
        assert r.id and r.name
        assert r.level in ("red", "yellow")
        assert r.groups and all(g for g in r.groups)


def test_chest_pain_with_cold_sweat_is_red():
    result = assess("我最近胸痛，还出冷汗，感觉左边胳膊都发麻")
    assert result.level == "red"
    assert result.matched


def test_chest_pain_alone_is_yellow_not_red():
    result = assess("偶尔有点胸痛")
    assert result.level == "yellow"


def test_sudden_severe_headache_with_vomiting_is_red():
    result = assess("突然头痛剧烈，还呕吐了两次")
    assert result.level == "red"


def test_hematemesis_is_red():
    result = assess("今天呕血了，大概有小半碗")
    assert result.level == "red"


def test_slurred_speech_one_side_weakness_is_red():
    result = assess("他说话口齿不清，右边手脚没有力气")
    assert result.level == "red"


def test_benign_text_is_none():
    result = assess("最近三天流鼻涕，嗓子有点疼，不发烧")
    assert result.level == "none"
    assert list(result.matched) == []


def test_red_wins_over_yellow_when_both_match():
    result = assess("胸痛带着左臂放射性疼痛，还有冷汗")
    assert result.level == "red"


def test_assess_never_calls_llm_it_is_pure_matching():
    source = Path(__file__).resolve().parents[1] / "rareguard" / "risk" / "rules.py"
    text = source.read_text(encoding="utf-8")
    assert "llm" not in text.lower()
    assert "openai" not in text.lower()
