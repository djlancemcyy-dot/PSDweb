@echo off
title 打包小帆船送审系统 (免安装绿色完整版)
cd /d "%~dp0"

if exist "%~dp0runtime\python.exe" (
    "%~dp0runtime\python.exe" package_tool.py
) else (
    python package_tool.py
)

pause
