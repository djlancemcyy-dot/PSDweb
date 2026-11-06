# -*- coding: utf-8 -*-
"""
package_tool.py — 小帆船送审系统自动化脱敏打包与版本备份工具
功能：
1. 自动读取并显示当前版号 (VERSION)；
2. 迭代安全保障：检测旧版本发布包，并在独立备份文件夹中自动归档 (旧版本新建文件夹备份)；
3. 自动归档当前源码、模版配置与数据快照至 backups/backup_vX.X.X_{date}/；
4. 使用 Python 内置 zipfile 压缩，彻底解决 Windows CMD 批处理编码乱码与路径截断问题。
"""

import os
import sys
import time
import shutil
import zipfile
import datetime
from pathlib import Path

def get_current_version(root_dir: Path) -> str:
    ver_file = root_dir / "VERSION"
    if ver_file.exists():
        try:
            return ver_file.read_text(encoding="utf-8").strip()
        except Exception:
            return "v2.3.0"
    return "v2.3.0"

def print_banner(version: str):
    print("=" * 68)
    print(f"   小帆船送审图稿制作系统 (PSDweb) — 自动化离线绿色打包与版本管理")
    print(f"   当前迭代版号: {version}")
    print("   包含: 随包独立免安装 Python 运行时 + AI 抠图模型 + 分层 PSD 引擎")
    print("=" * 68)
    print()

def backup_old_releases(parent_dir: Path, root_dir: Path, current_version: str):
    """
    每次迭代前，检测历史版本并新建独立文件夹备份归档
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. 在上级发布目录归档旧版压缩包
    archive_dir = parent_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    existing_zips = list(parent_dir.glob("小帆船送审系统_*.zip"))
    if existing_zips:
        backup_folder_name = f"backup_releases_{timestamp}"
        target_backup_dir = archive_dir / backup_folder_name
        target_backup_dir.mkdir(parents=True, exist_ok=True)
        print(f"[*] 发现旧版本发布包，正在新建文件夹归档备份至:")
        print(f"    -> {target_backup_dir}")
        for old_zip in existing_zips:
            try:
                dest = target_backup_dir / old_zip.name
                shutil.move(str(old_zip), str(dest))
                print(f"    [归档成功] {old_zip.name} -> {target_backup_dir.name}/")
            except Exception as e:
                print(f"    [!] 归档警告: {e}")
        print()
        
    # 2. 在项目内 backups/ 建立当前版本源码与配置的快照备份
    backups_dir = root_dir / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir = backups_dir / f"backup_{current_version}_{timestamp}"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    
    # 备份核心关键配置与源码
    files_to_snapshot = [
        "server.py",
        "shoe_cutout_engine.py",
        "VERSION",
        "requirements.txt",
        "SDD.md",
        "一键启动.bat",
        "打包给朋友.bat"
    ]
    for fn in files_to_snapshot:
        src = root_dir / fn
        if src.exists():
            shutil.copy2(src, snapshot_dir / fn)
            
    # 备份当前 data 配置
    data_dir = root_dir / "data"
    if data_dir.exists():
        shutil.copytree(data_dir, snapshot_dir / "data", dirs_exist_ok=True)
        
    print(f"[+] 当前版本 ({current_version}) 源码与业务配置已独立快照备份至:")
    print(f"    -> {snapshot_dir}")
    print()

def main():
    root_dir = Path(__file__).resolve().parent
    parent_dir = root_dir.parent
    version = get_current_version(root_dir)
    print_banner(version)
    
    # 执行旧版本新建文件夹备份
    backup_old_releases(parent_dir, root_dir, version)
    
    zip_filename = f"小帆船送审系统_免安装绿色完整版_{version}.zip"
    zip_path = parent_dir / zip_filename
    
    print(f"[*] 项目根目录: {root_dir}")
    print(f"[*] 当前发布包保存目标: {zip_path}")
    print()
    
    # 检查核心运行组件
    runtime_py = root_dir / "runtime" / "python.exe"
    if not runtime_py.exists():
        print("[!] 警告: 未在项目内找到 runtime/python.exe，随包运行环境可能不完整！")
    else:
        print("[+] 检测到随包独立绿色 Python 运行环境: 正常就绪")
        
    models_dir = root_dir / "models"
    model_count = len(list(models_dir.glob("*.onnx")))
    print(f"[+] 检测到离线 AI 抠图模型: 共 {model_count} 个 ONNX 模型")
    
    # 排除规则
    EXCLUDE_DIRS = {"__pycache__", ".git", ".idea", ".vscode", "backups"}
    EXCLUDE_EXTS = {".pyc", ".tmp", ".log"}
    
    print()
    print(f"[*] 正在执行【{version}】全量离线绿色打包，请稍候...")
    t0 = time.time()
    
    total_files = 0
    total_bytes = 0
    
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for foldername, subfolders, filenames in os.walk(root_dir):
            subfolders[:] = [d for d in subfolders if d not in EXCLUDE_DIRS]
            
            rel_folder = os.path.relpath(foldername, root_dir)
            if rel_folder == ".":
                rel_folder = ""
                
            # output 目录保留空目录标记，不打包历史测试生成的巨大文件
            if rel_folder == "output" or rel_folder.startswith("output" + os.sep):
                zinfo = zipfile.ZipInfo(os.path.join(rel_folder, ".keep").replace("\\", "/"))
                zinfo.date_time = time.localtime(time.time())[:6]
                zf.writestr(zinfo, "")
                continue
                
            for filename in filenames:
                file_ext = os.path.splitext(filename)[1].lower()
                if file_ext in EXCLUDE_EXTS:
                    continue
                if filename == zip_filename:
                    continue
                if filename.startswith("test_") or filename.startswith("benchmark"):
                    continue
                    
                abs_file = Path(foldername) / filename
                rel_file = os.path.relpath(abs_file, root_dir)
                arcname = rel_file.replace("\\", "/")
                zf.write(abs_file, arcname=arcname)
                
                total_files += 1
                total_bytes += abs_file.stat().st_size
                
                if total_files % 200 == 0:
                    mb_done = total_bytes / (1024 * 1024)
                    print(f"    已归档 {total_files} 个文件 ({mb_done:.1f} MB)...", end="\r")
                    
    duration = time.time() - t0
    zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
    raw_size_mb = total_bytes / (1024 * 1024)
    
    print()
    print("=" * 68)
    print(f" [OK] 版本 {version} 打包完成！")
    print(f"      归档文件总数: {total_files} 个")
    print(f"      原始体积:     {raw_size_mb:.2f} MB")
    print(f"      压缩后体积:   {zip_size_mb:.2f} MB")
    print(f"      耗时:         {duration:.2f} 秒")
    print(f"      输出发布包:   {zip_path}")
    print("=" * 68)
    print()
    print("【交付与使用说明】：")
    print(f"  1. 直接将该 zip 发布包 ({zip_path.name}) 发送给朋友或客户。")
    print("  2. 对方电脑无需配置 Python 或任何依赖，直接解压到任意文件夹。")
    print("  3. 双击解压目录中的【一键启动.bat】，2 秒内自动拉起服务并打开工作台！")
    print(f"  4. 软件设计说明书已同步放入根目录【SDD.md】，方便后续技术交接与二次开发。")
    print()
    
    try:
        os.system(f'explorer.exe /select,"{zip_path}"')
    except Exception:
        pass

if __name__ == "__main__":
    main()
