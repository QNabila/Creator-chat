# Agent Instructions

## Project

`creator-chat` is a local full-stack web app for loading a YouTube creator's latest 40 videos and chatting with an AI assistant that answers in that creator's voice using retrieved transcripts and clearly labeled extrapolation when needed.

The target stack is:

- Backend: Python, FastAPI
- Frontend: plain HTML, CSS, and vanilla JavaScript
- Transcript fetching: `yt-dlp`
- Embeddings: local `sentence-transformers` using `all-MiniLM-L6-v2`
- Vector store: persistent local ChromaDB
- LLM: Gemini 2.5 Flash through `google-generativeai`

Do not introduce paid embedding APIs or OpenAI dependencies for this project. Embeddings must run locally.

## Expected File Structure

Keep the project simple and flat:

```text
creator-chat/
├── main.py
├── ingest.py
├── retriever.py
├── chat.py
├── config.py
├── requirements.txt
├── .env.example
├── static/
│   ├── index.html
│   ├── style.css
│   └── app.js
└── README.md
```

## Core Behavior

- Users paste a YouTube channel URL and creator name.
- The app fetches transcripts from the latest 40 videos with `yt-dlp`.
- Captions should prefer English and fall back to auto-generated subtitles.
- Transcript text must be cleaned before storage:
  - Strip timestamps and caption markup.
  - Remove repeated caption lines.
  - Remove tags such as `[Music]`.
- Chunks must preserve metadata for `video_id`, `video_title`, `video_url`, and publish date when available.
- Store embeddings in persistent ChromaDB at `CHROMA_PATH`; do not use in-memory storage.
- Retrieval should use the same local embedding model as ingestion.
- Chat answers should use retrieved transcript chunks first.
- If retrieved content is partial or missing, the assistant should still answer in the creator's voice while clearly labeling extrapolation.

## Backend Contract

Implement these routes in `main.py`:

- `POST /ingest`
  - Body: `{ "channel_url": str, "creator_name": str }`
  - Returns ingestion status, processed video count, stored chunk count, and creator name.
- `POST /chat`
  - Body: `{ "question": str, "creator_name": str }`
  - Returns answer and source links.
- `GET /creators`
  - Returns loaded creator collections.
- `DELETE /creator/{creator_name}`
  - Deletes the matching creator collection.

Use `python-dotenv` to load `GEMINI_API_KEY` from `.env`.

## Configuration Defaults

Use these defaults unless there is a good reason to change them:

```python
CHUNK_SIZE = 500
CHUNK_OVERLAP = 80
TOP_K = 8
EMBED_MODEL = "all-MiniLM-L6-v2"
GEMINI_MODEL = "gemini-2.5-flash"
CHROMA_PATH = "./chroma_store"
MAX_VIDEOS = 40
```

## Gemini Prompt Rules

Gemini should receive a system instruction that says the assistant:

- Answers from retrieved transcript chunks when they clearly cover the question.
- Extends from the creator's visible principles and frameworks when coverage is partial.
- Still answers in the creator's voice when content is missing, but opens with one sentence acknowledging extrapolation.
- Never invents direct quotes, video titles, statistics, events, or claims as if they were explicitly in the videos.

## Frontend Expectations

Serve the frontend from FastAPI with `StaticFiles`; do not add a separate frontend build system.

The UI has two states:

- No creator loaded:
  - Centered creator loading form.
  - YouTube channel URL input.
  - Creator name input.
  - Load button and ingestion status.
- Creator loaded:
  - Header with active creator name and switch button.
  - Scrollable chat thread.
  - User messages right-aligned.
  - Assistant messages left-aligned.
  - Optional collapsible source links.
  - Bottom input bar with Enter-to-send support.

Visual direction:

- Use only black, white, and the red accent `#e50914`.
- Background: `#000000`
- Main text: `#ffffff`
- Accent: `#e50914`
- Font: Inter
- Keep the app responsive and tool-like. Avoid decorative UI.

## Error Handling

- Skip videos with no transcript and log that condition.
- Warn the user if fewer than 5 videos have usable transcripts.
- Cap ingestion at `MAX_VIDEOS`.
- If Gemini fails, show a generic retry message in the chat.
- If the user asks a question before loading a creator, show `Load a creator first`.

## Development Commands

Set up:

```bash
pip install -r requirements.txt
cp .env.example .env
```

Run:

```bash
uvicorn main:app --reload
```

Open:

```text
http://localhost:8000
```

The first ingestion run will download the local embedding model, which is roughly 80 MB.

## Implementation Notes

- Prefer small, focused modules matching the expected file structure.
- Use `chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction` so ChromaDB owns embedding calls consistently.
- Keep collection names stable and derived from creator names or channel identifiers.
- Avoid global mutable request state except for lightweight app configuration.
- Preserve source metadata through ingestion, retrieval, and chat response formatting.
- Add tests where behavior is easy to isolate, especially transcript cleaning, chunking, and three-tier prompt behavior.
