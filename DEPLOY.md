# Anja deployment

## Why the downloaded UI showed Offline

`frontend/index.html` is only the browser interface. It calls the FastAPI backend at `/api/...`.
Opening the HTML directly with `file://` does not start FastAPI, so the browser cannot reach the API.

## Local Windows

1. Install Python 3.13.
2. Open Command Prompt in this folder.
3. Run:

   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   copy .env.example .env

4. Put your API key in `.env`:
   OPENAI_API_KEY=...
   ANJA_MODEL=gpt-5

5. Run:
   python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000

6. Open:
   http://127.0.0.1:8000

Do NOT double-click frontend/index.html.

## Render production deployment

1. Push the complete folder to a GitHub repository.
2. Render -> New -> Web Service -> select the repository.
3. Runtime: Python 3.
4. Build:
   pip install -r requirements.txt
5. Start:
   uvicorn backend.app:app --host 0.0.0.0 --port $PORT
6. Add secret:
   OPENAI_API_KEY = your OpenAI API key
7. Add:
   ANJA_MODEL = gpt-5
8. Deploy.
9. Open the generated https://....onrender.com URL.

The included render.yaml can be used as a Blueprint.

## Important production note

The default Render filesystem is ephemeral. Uploaded files and JSON memory should not be treated as durable production storage. For a real multi-user Anja, use object storage for uploads and Postgres/Redis for persistent memory/session state.

## What the next production layer should add

- OpenAI Responses API adapter
- Web search tool
- File Search / vector retrieval
- Code interpreter
- durable object storage
- Postgres memory
- authentication
- per-user sessions
- streaming responses
- rate limits
- audit/security controls
