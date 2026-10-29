@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Dayflow 闲鱼自动上架与 24h 自动发货助手

echo ======================================================================
echo       Dayflow - 闲鱼 (Goofish) 自动上架与 24h 夸克网盘自动发货助手
echo ======================================================================
echo   绑定的夸克网盘链接: https://pan.quark.cn/s/3ad86edcaa2a
echo   提取码: zrSv   口令: /~90903bswYi~:/
echo ======================================================================
echo.
echo   [1] 启动 24 小时自动发货机器人 (监控闲鱼消息并自动发送夸克网盘链接)
echo   [2] 一键发布/上架 Dayflow 到闲鱼 (生成首图 + 自动复制文案 + 打开闲鱼)
echo   [3] 仅生成宣传首图并预览上架文案与发货话术
echo.
set /p choice="请输入数字 [1/2/3] (直接回车默认选 1): "

if "%choice%"=="2" (
    .\.venv\Scripts\python.exe -m xianyu_bot.bot --mode publish
) else if "%choice%"=="3" (
    .\.venv\Scripts\python.exe -m xianyu_bot.bot --mode preview
    pause
) else (
    .\.venv\Scripts\python.exe -m xianyu_bot.bot --mode watch
)
