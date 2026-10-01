@echo off
setlocal
cd /d "%~dp0"

where ollama >nul 2>&1
if errorlevel 1 (
  echo Ollama is not installed.
  echo Install it from https://ollama.com/download/windows
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating Anja Python environment...
  python -m venv .venv
  if errorlevel 1 (
    echo Python is not installed or not available in PATH.
    pause
    exit /b 1
  )
  call ".venv\Scripts\activate.bat"
  python -m pip install -r requirements.txt
) else (
  call ".venv\Scripts\activate.bat"
)

echo Checking the local Anja model...
ollama pull gemma3:4b

set ANJA_PROVIDER=ollama
set OLLAMA_MODEL=gemma3:4b

echo.
echo Starting Anja at http://127.0.0.1:8000
echo Keep this window open while using Anja.
echo.
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000

pause
