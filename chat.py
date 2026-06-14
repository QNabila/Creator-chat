import os
from typing import Any

from config import GEMINI_MODEL, GEMINI_TEMPERATURE, MIN_RELEVANCE_SCORE
from style_profile import format_style_profile, load_style_profile


def fallback_answer(creator_name: str) -> str:
    return f"I couldn't find {creator_name} covering this in the loaded videos."


def filter_relevant_chunks(
    chunks: list[dict[str, Any]],
    min_relevance_score: float = MIN_RELEVANCE_SCORE,
) -> list[dict[str, Any]]:
    relevant: list[dict[str, Any]] = []
    for chunk in chunks:
        score = chunk.get("similarity_score")
        if isinstance(score, (int, float)) and score >= min_relevance_score:
            relevant.append(chunk)
    return relevant


def build_generation_config() -> dict[str, float]:
    return {"temperature": GEMINI_TEMPERATURE}


def build_system_prompt(
    creator_name: str,
    chunks: list[dict[str, Any]],
    style_profile: dict[str, Any] | None = None,
) -> str:
    content = "\n\n".join(
        (
            f"Source {index + 1} "
            f"({chunk.get('video_title', 'Untitled video')}, relevance {chunk.get('similarity_score', 0):.2f}): "
            f"{chunk.get('chunk_text', '')}"
        )
        for index, chunk in enumerate(chunks)
    )
    style = format_style_profile(style_profile)
    return f"""You are a learning assistant built strictly on {creator_name}'s public YouTube content.

Rules:
- Answer ONLY using the content provided below. Do not use outside knowledge.
- Treat weak, tangential, or merely stylistically similar context as not found.
- If the answer is not covered in the content, say exactly: "{fallback_answer(creator_name)}"
- Mirror {creator_name}'s teaching style, tone, and frameworks only when they appear in the retrieved content.
- Use the style profile only for tone and structure, never for facts or claims.
- Where relevant, reference the specific idea or concept from the content (not the video title unless it adds clarity).
- Be direct. No filler. No hedging beyond what the content warrants.

Style profile from loaded transcripts:
---
{style}
---

Content from {creator_name}'s videos:
---
{content}
---"""


def unique_sources(chunks: list[dict[str, Any]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    sources: list[dict[str, str]] = []
    for chunk in chunks:
        title = str(chunk.get("video_title") or "Untitled video")
        url = str(chunk.get("video_url") or "")
        key = (title, url)
        if key in seen:
            continue
        seen.add(key)
        sources.append({"title": title, "url": url})
    return sources


def answer_question(question: str, chunks: list[dict[str, Any]], creator_name: str) -> dict[str, Any]:
    relevant_chunks = filter_relevant_chunks(chunks)
    if not relevant_chunks:
        return {"answer": fallback_answer(creator_name), "sources": []}

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=build_system_prompt(creator_name, relevant_chunks, load_style_profile(creator_name)),
        generation_config=build_generation_config(),
    )
    response = model.generate_content(question)
    answer = (getattr(response, "text", "") or "").strip()
    if not answer:
        answer = fallback_answer(creator_name)

    return {"answer": answer, "sources": unique_sources(relevant_chunks)}
