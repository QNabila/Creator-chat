from style_profile import build_style_profile, format_style_profile, style_key


def test_style_key_is_stable():
    assert style_key("Alex Hormozi!") == "alex_hormozi"


def test_build_style_profile_extracts_basic_signals():
    profile = build_style_profile(
        "Creator",
        [
            "Here's the thing. You need to focus. The point is simple.",
            "You need to do the work.",
        ],
    )

    assert profile["creator_name"] == "Creator"
    assert profile["avg_sentence_words"] > 0
    assert "you need to" in profile["common_phrases"]


def test_format_style_profile_warns_against_facts():
    text = format_style_profile({"avg_sentence_words": 5, "common_phrases": ["you need to"], "style_note": "No facts."})

    assert "Average sentence length" in text
    assert "you need to" in text
    assert "No facts." in text

