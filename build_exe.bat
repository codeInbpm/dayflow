@echo off
setlocal
cd /d "%~dp0"

echo ===================================================
echo   Dayflow - Windows One-Click Packaging Tool
echo ===================================================

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment .venv not found.
    pause
    exit /b 1
)

echo [1/2] Building Vue 3 frontend bundle...
call npm --prefix frontend run build
if errorlevel 1 (
    echo [ERROR] Frontend build failed!
    pause
    exit /b 1
)

echo [2/2] Building standalone Dayflow.exe and uninst.exe...
".venv\Scripts\python.exe" scripts\build_exe.py
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed!
    pause
    exit /b 1
)

echo.
echo ===================================================
echo   Build Complete! Output files in release\:
echo   - %~dp0release\Dayflow.exe
echo   - %~dp0release\uninst.exe
echo   - %~dp0release\Dayflow-Windows-v1.0.0.zip
echo ===================================================
