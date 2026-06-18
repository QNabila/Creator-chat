# Creator Chat

Creator Chat is a local web app that loads a YouTube creator's recent transcripts and lets you chat with an assistant that answers in that creator's voice.

## Prerequisites

- Python 3.10+
- pip
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/)

## Install

```bash
pip install -r requirements.txt
cp .env.example .env
```

Add your Gemini API key to `.env`:

```text
GEMINI_API_KEY=your_key_here
```

## Run

```bash
uvicorn main:app --reload --port 8001
```

Open:

```text
http://localhost:8001
```

## Usage

1. Paste a YouTube channel URL.
2. Enter the creator name.
3. Click **Load Creator**.
4. Wait while transcripts are fetched, chunked, embedded, and saved locally.
5. Ask questions in the chat.

The load screen shows the current ingestion stage and progress. The chat box opens after the creator finishes loading.

If the creator already exists, the app asks whether to use the existing data or re-ingest the creator.

The assistant uses a three-tier answer policy: direct transcript-backed answers when available, principled extension when the videos partially cover a topic, and clearly labeled extrapolation when the loaded videos do not directly cover it.

## Vercel Frontend Preview

This project can deploy the static frontend to Vercel, but the working ingestion and chat backend still runs locally with FastAPI.

- Do not add `GEMINI_API_KEY` to Vercel for the frontend-only preview.
- The Vercel page is a UI preview unless it is connected to a hosted HTTPS backend.
- For the full app locally, keep FastAPI running at `http://localhost:8001`.
- If deploying with the Vercel CLI, use the lowercase project name:

```bash
npx vercel --prod --yes --name creator-chat
```

## Notes

- The app uses `yt-dlp` and does not require a YouTube API key.
- Auto-captions or subtitles must be enabled on the creator's videos.
- Ingestion is capped at the latest 40 videos.
- ChromaDB data is stored in `./chroma_store`, so creators remain available after restarting the app.
- The first run downloads the `all-MiniLM-L6-v2` embedding model, which is roughly 80 MB.
