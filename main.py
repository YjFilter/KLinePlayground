"""
K-Line Playground - 统一启动入口
支持桌面端应用与 Web 服务两种运行模式。

使用方法:
  1. 默认桌面端模式:
     python main.py
     python main.py --mode desktop

  2. 纯 Web 服务模式:
     python main.py --mode web
     python main.py --mode web --port 5000 --host 0.0.0.0
"""
from __future__ import annotations

import os
import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main():
    parser = argparse.ArgumentParser(
        description="K-Line Playground - 桌面端与 Web 端双模统一入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  python main.py                 # 启动独立桌面客户端 (默认)
  python main.py --mode web      # 启动纯 Web 服务器
  python main.py --port 5002     # 指定服务端口
"""
    )
    parser.add_argument(
        "--mode",
        choices=["desktop", "web"],
        default="desktop",
        help="运行模式: 'desktop' (唤起桌面原生窗口) 或 'web' (纯 Web 服务器，默认 desktop)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="指定监听端口（Web模式默认 5000，桌面模式默认自动探测可用端口）"
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="指定监听地址（Web模式默认 0.0.0.0，桌面模式默认 127.0.0.1）"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="开启调试模式"
    )
    args = parser.parse_args()

    # 确保本地数据目录就绪
    os.makedirs(PROJECT_ROOT / "data", exist_ok=True)
    os.makedirs(PROJECT_ROOT / "users", exist_ok=True)

    if args.mode == "desktop":
        from desktop.desktop_app import launch_desktop
        host = args.host or "127.0.0.1"
        launch_desktop(host=host, port=args.port, debug=args.debug)
    else:
        from backend.app_enhanced import app
        host = args.host or "0.0.0.0"
        port = args.port or 5000
        print("\n" + "=" * 66)
        print(f"  ★ K-Line Playground Web 服务已启动！")
        print(f"  ★ 本地访问地址:   http://127.0.0.1:{port}")
        if host == "0.0.0.0":
            print(f"  ★ 局域网访问地址: http://0.0.0.0:{port} (同一局域网设备可用)")
        print(f"  ★ 提示: 按 Ctrl+C 可停止服务")
        print("=" * 66 + "\n")
        app.run(host=host, port=port, debug=args.debug)


if __name__ == "__main__":
    main()
