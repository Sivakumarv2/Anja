# Anja — Free Local AI Setup

Anja now supports a zero-API-credit local mode using Ollama.

## Windows setup

1. Install Ollama:
https://ollama.com/download/windows

2. Open PowerShell and download the recommended multimodal model:

    ollama pull gemma3:4b

3. Clone/open this repository and create the Python environment:

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt

4. Start Anja:

    $env:ANJA_PROVIDER="ollama"
    $env:OLLAMA_MODEL="gemma3:4b"
    python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000

5. Open:

    http://127.0.0.1:8000

Anja will use the local Ollama model. No OpenAI API credits are required.

## Check status

Open:

    http://127.0.0.1:8000/api/status

Expected provider:

    ollama

## Notes

- Text chat works locally.
- Images can be analyzed by multimodal Ollama models such as Gemma 3.
- PDF, DOCX, TXT, Markdown, CSV and JSON files are locally extracted and supplied to the model.
- Anja memory remains local to the running installation.
- The Railway deployment cannot access Ollama running on your personal PC. The completely free setup therefore runs Anja locally.
- OpenAI remains available as an optional provider later.
