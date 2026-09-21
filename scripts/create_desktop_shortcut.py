"""
为 K-Line Playground 生成 Windows 桌面快捷方式 (带图标、双击即开、无黑框后台窗口)
"""
import os
import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_windows_shortcut(
    shortcut_name: str = "K-Line Playground",
    target: str = None,
    arguments: str = "",
    icon_path: str = None,
    working_dir: str = None
) -> str:
    desktop_dir = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop")
    lnk_path = os.path.join(desktop_dir, f"{shortcut_name}.lnk")

    target = target or os.path.join(sys.prefix, "Scripts", "pythonw.exe")
    if not os.path.exists(target):
        target = sys.executable

    working_dir = working_dir or str(PROJECT_ROOT)
    arguments = arguments or f'"{PROJECT_ROOT / "run_desktop.py"}"'
    icon_path = icon_path or str(PROJECT_ROOT / "frontend" / "assets" / "favicon.ico")
    if not os.path.exists(icon_path):
        icon_path = str(PROJECT_ROOT / "installer_source" / "favicon.ico")

    # 使用 Windows 原生 PowerShell WScript.Shell 创建标准 .lnk 快捷方式
    ps_cmd = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{lnk_path}')
$Shortcut.TargetPath = '{target}'
$Shortcut.Arguments = '{arguments}'
$Shortcut.WorkingDirectory = '{working_dir}'
$Shortcut.IconLocation = '{icon_path}, 0'
$Shortcut.Description = 'K-Line Playground 复盘与实时看盘终端'
$Shortcut.Save()
"""
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=True)
    return lnk_path


if __name__ == "__main__":
    lnk = create_windows_shortcut()
    print(f"★ 成功在桌面创建应用快捷方式: {lnk}")
