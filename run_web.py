"""
K-Line Playground - Web 端便捷启动入口 (无桌面窗口，纯 Web 服务器)
用法: python run_web.py [--port 5000] [--host 0.0.0.0]
"""
import os
import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main():
    parser = argparse.ArgumentParser(description="K-Line Playground Web 服务启动器")
    parser.add_argument("--port", type=int, default=5000, help="Web 服务监听端口（默认 5000）")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Web 服务监听地址（默认 0.0.0.0）")
    parser.add_argument("--debug", action="store_true", default=False, help="开启 Flask 调试模式")
    args = parser.parse_args()

    # 确保本地数据目录就绪
    os.makedirs(PROJECT_ROOT / "data", exist_ok=True)
    os.makedirs(PROJECT_ROOT / "users", exist_ok=True)

    from backend.app_enhanced import app

    print("\n" + "=" * 66)
    print(f"  ★ K-Line Playground Web 服务已启动！")
    print(f"  ★ 本地访问地址:   http://127.0.0.1:{args.port}")
    if args.host == "0.0.0.0":
        print(f"  ★ 局域网访问地址: http://0.0.0.0:{args.port} (同一局域网设备可用)")
    print(f"  ★ 提示: 按 Ctrl+C 可停止服务")
    print("=" * 66 + "\n")

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
