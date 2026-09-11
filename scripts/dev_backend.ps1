# Runs the backend API locally with auto-reload.
Set-Location "$PSScriptRoot\..\backend"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt -q
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
