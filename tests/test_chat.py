import sys
from types import ModuleType

from chat import (
    answer_question,
    build_generation_config,
    build_system_prompt,
    unique_sources,
)


def test_build_system_prompt_includes_three_tier_logic_and_content():
    prompt = build_system_prompt(
        "Alex Hormozi",
        [{"chunk_text": "Offer beats tactics.", "video_title": "Offers", "similarity_score": 0.72}],
        {"avg_sentence_words": 8.5, "common_phrases": ["the point is"], "style_note": "Direct."},
    )

    assert "CLEARLY COVERED" in prompt
    assert "PARTIALLY COVERED" in prompt
    assert "NOT COVERED" in prompt
    assert "Never stop with" in prompt
    assert "Do not present extrapolation as something the videos directly said" in prompt
    assert "Offer beats tactics." in prompt
    assert "the point is" in prompt


def test_build_system_prompt_handles_empty_chunks():
    prompt = build_system_prompt("Alex Hormozi", [])

    assert "No retrieved transcript chunks were available" in prompt
    assert "extrapolating from Alex Hormozi's overall style and principles" in prompt


def test_answer_question_calls_gemini_even_for_empty_chunks(monkeypatch):
    calls = {}

    class FakeModel:
        def __init__(self, **kwargs):
            calls["kwargs"] = kwargs

        def generate_content(self, question):
            calls["question"] = question
            return type("Response", (), {"text": "The loaded videos do not directly cover this, so I am extrapolating."})()

    fake_google = ModuleType("google")
    fake_genai = ModuleType("google.generativeai")

    def configure(api_key):
        calls["api_key"] = api_key

    fake_genai.configure = configure
    fake_genai.GenerativeModel = FakeModel
    fake_google.generativeai = fake_genai

    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.generativeai", fake_genai)

    result = answer_question("What should I do?", [], "Alex Hormozi")

    assert calls["api_key"] == "fake-key"
    assert calls["question"] == "What should I do?"
    assert "system_instruction" in calls["kwargs"]
    assert result["sources"] == []
    assert "extrapolating" in result["answer"]


def test_generation_config_uses_low_temperature():
    assert build_generation_config()["temperature"] == 0.1


def test_unique_sources_deduplicates_by_title_and_url():
    chunks = [
        {"video_title": "A", "video_url": "https://example.com/a"},
        {"video_title": "A", "video_url": "https://example.com/a"},
        {"video_title": "B", "video_url": "https://example.com/b"},
    ]

    assert unique_sources(chunks) == [
        {"title": "A", "url": "https://example.com/a"},
        {"title": "B", "url": "https://example.com/b"},
    ]
