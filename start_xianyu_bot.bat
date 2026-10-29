@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m xianyu_bot.bot %*
) else (
    python -m xianyu_bot.bot %*
)
