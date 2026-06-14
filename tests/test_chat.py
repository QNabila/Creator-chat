from chat import (
    answer_question,
    build_generation_config,
    build_system_prompt,
    fallback_answer,
    filter_relevant_chunks,
    unique_sources,
)


def test_fallback_answer_exact_text():
    assert fallback_answer("Alex Hormozi") == "I couldn't find Alex Hormozi covering this in the loaded videos."


def test_build_system_prompt_includes_strict_rules_and_content():
    prompt = build_system_prompt(
        "Alex Hormozi",
        [{"chunk_text": "Offer beats tactics.", "video_title": "Offers", "similarity_score": 0.72}],
        {"avg_sentence_words": 8.5, "common_phrases": ["the point is"], "style_note": "Direct."},
    )

    assert "Answer ONLY using the content provided below" in prompt
    assert "Treat weak, tangential" in prompt
    assert "Use the style profile only for tone and structure" in prompt
    assert 'say exactly: "I couldn\'t find Alex Hormozi covering this in the loaded videos."' in prompt
    assert "Offer beats tactics." in prompt
    assert "the point is" in prompt


def test_filter_relevant_chunks_removes_weak_matches():
    chunks = [
        {"chunk_text": "weak", "similarity_score": 0.2},
        {"chunk_text": "strong", "similarity_score": 0.8},
        {"chunk_text": "missing score"},
    ]

    assert filter_relevant_chunks(chunks, min_relevance_score=0.35) == [{"chunk_text": "strong", "similarity_score": 0.8}]


def test_answer_question_returns_fallback_for_weak_chunks_without_gemini(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = answer_question(
        "What should I do?",
        [{"chunk_text": "Unrelated context", "similarity_score": 0.1}],
        "Alex Hormozi",
    )

    assert result == {"answer": "I couldn't find Alex Hormozi covering this in the loaded videos.", "sources": []}


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
