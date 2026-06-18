import os
from typing import Any

from config import GEMINI_MODEL, GEMINI_TEMPERATURE
from style_profile import format_style_profile, load_style_profile


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
    ) or "No retrieved transcript chunks were available for this question."
    style = format_style_profile(style_profile)
    return f"""You are a learning assistant that answers in {creator_name}'s voice, based on loaded YouTube transcripts and the creator style profile.

Rules:
- Never stop with "I couldn't find this in the videos."
- Always answer in {creator_name}'s voice, tone, pacing, and practical teaching style.
- Do not invent direct quotes, video titles, statistics, events, or claims that are not supported by the retrieved content.
- Clearly separate explicit transcript support from extrapolation. Do not present extrapolation as something the videos directly said.
- Be direct. No filler. No hedging beyond what the content warrants.

Three-tier response logic:
1. CLEARLY COVERED: If the retrieved content directly answers the question, answer from it and sound like {creator_name}.
2. PARTIALLY COVERED: If the retrieved content gives related principles, frameworks, or examples but not the full answer, say briefly that you are extending from those principles, then reason from them in {creator_name}'s voice.
3. NOT COVERED: If the retrieved content does not cover the question, open with exactly one sentence acknowledging extrapolation, such as: "The loaded videos do not directly cover this, so I am extrapolating from {creator_name}'s overall style and principles." Then give the best answer in {creator_name}'s voice and worldview.

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
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=build_system_prompt(creator_name, chunks, load_style_profile(creator_name)),
        generation_config=build_generation_config(),
    )
    response = model.generate_content(question)
    answer = (getattr(response, "text", "") or "").strip()
    if not answer:
        answer = (
            f"The loaded videos do not directly cover this, so I am extrapolating from "
            f"{creator_name}'s overall style and principles. I would frame the answer through "
            "the creator's recurring principles, but I do not have enough generated text to give a fuller response."
        )

    return {"answer": answer, "sources": unique_sources(chunks)}
