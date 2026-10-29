@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ===================================================
echo   Dayflow - Windows 桌面应用一键打包工具
echo ===================================================

if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未检测到 .venv 虚拟环境，请先创建虚拟环境。
    pause
    exit /b 1
)

echo [1/2] 正在构建 Vue 3 前端生产静态资源 (frontend/dist)...
call npm --prefix frontend run build
if errorlevel 1 (
    echo [错误] 前端构建失败！
    pause
    exit /b 1
)

echo [2/2] 正在打包独立单文件可执行程序 (release\Dayflow.exe)...
".venv\Scripts\python.exe" scripts\build_exe.py
if errorlevel 1 (
    echo [错误] PyInstaller 打包失败！
    pause
    exit /b 1
)

echo.
echo ===================================================
echo   打包完成！
echo   独立单文件可执行程序位置：
echo   %~dp0release\Dayflow.exe
echo   直接将该 Dayflow.exe 发给他人即可双击运行！
echo ===================================================
