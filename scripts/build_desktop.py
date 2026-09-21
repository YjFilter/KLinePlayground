"""
KLineStudio - 桌面端应用打包构建脚本 (PyInstaller)
用于将应用编译并打包为独立的 Windows 桌面客户端目录与安装分发包。
"""
from __future__ import annotations

import os
import sys
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def build():
    print("=" * 66)
    print("  开始打包 KLineStudio Windows 桌面客户端...")
    print("=" * 66)

    # 检查 PyInstaller
    try:
        import PyInstaller
    except ImportError:
        print("[!] 检测到未安装 pyinstaller，正在安装...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    icon_path = PROJECT_ROOT / "frontend" / "assets" / "favicon.ico"
    if not icon_path.exists():
        icon_path = PROJECT_ROOT / "installer_source" / "favicon.ico"

    entry_point = str(PROJECT_ROOT / "main.py")
    dist_dir = str(PROJECT_ROOT / "dist")
    build_dir = str(PROJECT_ROOT / "build")

    # 构建 PyInstaller 参数
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", "KLineStudio",
        f"--icon={icon_path}",
        f"--add-data={PROJECT_ROOT / 'frontend'}{os.pathsep}frontend",
        f"--add-data={PROJECT_ROOT / 'data'}{os.pathsep}data",
        "--hidden-import=clr",
        "--hidden-import=webview",
        "--hidden-import=webview.platforms.winforms",
        "--hidden-import=engineio.async_drivers.threading",
        "--hidden-import=baostock",
        "--hidden-import=akshare",
        entry_point,
    ]

    print(f"执行命令: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=True)

    exe_path = PROJECT_ROOT / "dist" / "KLineStudio" / "KLineStudio.exe"
    print("\n" + "=" * 66)
    print(f"  ★ 打包完成！")
    print(f"  ★ 可执行文件路径: {exe_path}")
    print("=" * 66 + "\n")

    # 更新桌面快捷方式指向编译后的可执行程序
    from scripts.create_desktop_shortcut import create_windows_shortcut
    lnk = create_windows_shortcut(
        shortcut_name="K-Line Playground",
        target=str(exe_path),
        arguments="",
        icon_path=str(icon_path),
        working_dir=str(exe_path.parent)
    )
    print(f"  ★ 已同步更新桌面快捷方式: {lnk}")


if __name__ == "__main__":
    build()
