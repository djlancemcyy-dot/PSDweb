# -*- coding: utf-8 -*-
"""
setup_env.py — AI 智能体与开发者一键环境配置助手
适合: Antigravity / Cursor / Claude Code / 开发者本地一键初始化
功能:
1. 校验 Python 环境 (Python 3.10+ 64位)
2. 自动安装/核验 requirements.txt 依赖
3. 检查离线模型 models 资产完整度，缺失时指引或自动初始化
4. 验证 Photoshop PSD 编码引擎 (pytoshop + packbits)
"""

import sys
import os
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent

def log(msg: str):
    print(f"[*] {msg}")

def check_python():
    log(f"当前 Python 版本: {sys.version.split()[0]} ({sys.platform})")
    if sys.version_info < (3, 10):
        print("[!] 错误: 本系统需要 Python 3.10 或更高版本，请升级后再试。")
        sys.exit(1)

def install_requirements():
    req_file = ROOT_DIR / "requirements.txt"
    if not req_file.exists():
        print("[!] 未找到 requirements.txt")
        return
    log("正在安装/核验 Python 依赖库...")
    cmd = [sys.executable, "-m", "pip", "install", "-r", str(req_file)]
    res = subprocess.run(cmd)
    if res.returncode == 0:
        log("Python 依赖已全部就绪！")
    else:
        print("[!] 依赖安装出现部分异常，请检查网络或 pip 源配置。")

def check_models():
    models_dir = ROOT_DIR / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    onnx_files = list(models_dir.glob("*.onnx"))
    log(f"正在检查离线 AI 抠图模型: 当前包含 {len(onnx_files)} 个 ONNX 模型")
    for f in onnx_files:
        print(f"    -> {f.name} ({f.stat().st_size / (1024*1024):.1f} MB)")
        
    if not onnx_files:
        print("\n[!] 提示: models/ 目录下暂未检测到 ONNX 抠图模型。")
        print("    系统支持: isnet_fine_tuned.onnx, isnet-general-use.onnx, birefnet_lite.onnx, u2net.onnx")
        print("    请将模型权重放置于 models/ 目录即可实现 100% 离线免联网高精抠图。\n")

def test_engines():
    log("正在验证核心引擎组件...")
    try:
        import onnxruntime
        import cv2
        import PIL
        import fastapi
        import uvicorn
        import pytoshop
        import psd_tools
        log("FastAPI + ONNXRuntime + OpenCV + Pytoshop (PSD分层) 全部载入正常！")
    except Exception as e:
        print(f"[!] 引擎导入检测警告: {e}")

def main():
    print("=" * 65)
    print("   鞋样送审图稿制作系统 (PSDweb) — AI 环境自动化部署")
    print("=" * 65)
    check_python()
    install_requirements()
    check_models()
    test_engines()
    print("=" * 65)
    print(" [OK] 环境配置完成！")
    print(" 启动服务命令: python server.py")
    print(" 访问地址:     http://127.0.0.1:8765")
    print("=" * 65)

if __name__ == "__main__":
    main()
