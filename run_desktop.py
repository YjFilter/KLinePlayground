"""
KLineStudio - 桌面端便捷启动入口
用法: python run_desktop.py [--port PORT] [--debug]
"""
import sys
import argparse
from desktop.desktop_app import launch_desktop


def main():
    parser = argparse.ArgumentParser(description="KLineStudio 桌面端启动器")
    parser.add_argument("--port", type=int, default=None, help="指定本地服务端口（默认自动探测 5000+ 可用端口）")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="服务监听地址（默认 127.0.0.1）")
    parser.add_argument("--debug", action="store_true", help="开启调试模式（打开控制台检查器）")
    args = parser.parse_args()

    launch_desktop(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
