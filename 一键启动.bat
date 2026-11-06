@echo off
title 小帆船 - 鞋样送审图稿制作系统 [免安装绿色版]
cd /d "%~dp0"

echo ========================================================
echo    小帆船 - 鞋样送审图稿制作系统 [PSDweb v2.4]
echo    零依赖免安装绿色版 - 纯净秋知风格 - 局域网协同
echo    支持: 300DPI 送审大图 + Photoshop 100%% 可编辑分层 PSD
echo ========================================================
echo.

echo [1/3] 正在检查并释放后台 8765 端口...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" >nul 2>&1

echo [2/3] 正在探测运行引擎...

set "PYBIN="
if exist "%~dp0runtime\python.exe" (
    set "PYBIN=%~dp0runtime\python.exe"
    echo       已载入: 随包独立免安装运行引擎 [Zero-Dependency Runtime]
    goto LAUNCH
)

if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYBIN=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    echo       已载入: 本机 Python 3.12 运行环境
    goto LAUNCH
)

where python >nul 2>&1
if %ERRORLEVEL%==0 (
    set "PYBIN=python"
    echo       已载入: 系统全局 Python 环境
    goto LAUNCH
)

color 0C
echo.
echo ========================================================
echo [错误] 未检测到可用的运行引擎！
echo ========================================================
echo 请确保本文件夹内包含 runtime 目录，或者本机已安装 Python 3.10+。
echo.
pause
exit /b 1

:LAUNCH
echo [3/3] 正在唤醒本地离线服务...
echo.
echo       本机访问地址: http://127.0.0.1:8765
echo       AI 开放接口:   http://127.0.0.1:8765/docs
echo.
echo       如需退出，直接关闭本黑色控制台窗口即可。
echo ========================================================
echo.

start "" "http://127.0.0.1:8765"
"%PYBIN%" server.py
pause
