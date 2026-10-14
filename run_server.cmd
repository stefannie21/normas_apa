@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend --reload-dir frontend
) else (
  python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend --reload-dir frontend
)