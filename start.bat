@echo off
REM One-command start for Windows
cd /d "%~dp0backend"
if not exist .venv py -m venv .venv
call .venv\Scripts\python.exe -m pip install -r requirements.txt -q
if not exist .env copy .env.example .env
echo Reel Routes -^> http://127.0.0.1:8000
call .venv\Scripts\uvicorn app.main:app --reload
