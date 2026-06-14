import pytest

from ingest import chunk_text, clean_transcript, collection_name_for_creator


def test_clean_transcript_removes_caption_markup_and_noise():
    raw = """WEBVTT

00:00:01.000 --> 00:00:03.000
<v Speaker>Hello &amp; welcome</v>

00:00:03.000 --> 00:00:04.000
[Music]

00:00:04.000 --> 00:00:05.000
Hello &amp; welcome

2
00:00:05,000 --> 00:00:07,000
Build the thing.
"""

    assert clean_transcript(raw) == "Hello & welcome Build the thing."


def test_chunk_text_short_transcript_returns_one_chunk():
    assert chunk_text("one two three", chunk_size=5, overlap=1) == ["one two three"]


def test_chunk_text_applies_overlap():
    chunks = chunk_text("one two three four five six", chunk_size=4, overlap=2)

    assert chunks == ["one two three four", "three four five six"]


def test_chunk_text_rejects_invalid_overlap():
    with pytest.raises(ValueError):
        chunk_text("one two", chunk_size=2, overlap=2)


def test_collection_name_is_stable_and_chroma_safe():
    assert collection_name_for_creator("Alex Hormozi!") == "cc_alex_hormozi"

