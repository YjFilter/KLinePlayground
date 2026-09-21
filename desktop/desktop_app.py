"""
K-Line Playground Desktop Application Manager
使用 PyWebView + WebView2 启动独立的桌面原生窗口，并托管后台 Flask 本地服务。
支持动态端口探测、数据持久化存储、干净的生命周期退出与双模式 (Desktop + Web) 支持。
"""
from __future__ import annotations

import os
import sys
import time
import socket
import logging
import threading
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def find_free_port(start_port: int = 5000, max_attempts: int = 50) -> int:
    """从 start_port 开始探测首个可绑定的空闲本地端口"""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"在 {start_port} ~ {start_port + max_attempts} 范围内未找到可用端口")


def get_desktop_storage_path() -> str:
    """获取桌面端专用的 WebView2 用户数据持久化目录"""
    if sys.platform == 'win32':
        base_dir = os.environ.get('APPDATA', os.path.expanduser('~'))
        storage_dir = os.path.join(base_dir, 'KLinePlayground', 'webview_storage')
    else:
        storage_dir = os.path.expanduser('~/.kline-playground/webview_storage')
    os.makedirs(storage_dir, exist_ok=True)
    return storage_dir


def get_desktop_icon_path() -> Optional[str]:
    """寻找桌面端图标路径"""
    candidates = [
        PROJECT_ROOT / "frontend" / "assets" / "favicon.ico",
        PROJECT_ROOT / "installer_source" / "favicon.ico",
        PROJECT_ROOT / "ai_assistant.ico",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None


class DesktopServerManager:
    """托管 Flask 本地 WSGI 服务的管理器"""
    def __init__(self, host: str = '127.0.0.1', port: Optional[int] = None):
        self.host = host
        self.port = port if port is not None else find_free_port(5000)
        self.server = None
        self.thread: Optional[threading.Thread] = None
        self._is_running = False

    def start(self, timeout_sec: float = 8.0) -> str:
        """在后台守护线程启动 Flask 服务，并等待就绪"""
        from werkzeug.serving import make_server
        from backend.app_enhanced import app

        self.server = make_server(self.host, self.port, app, threaded=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True, name="FlaskDesktopServerThread")
        self.thread.start()
        self._is_running = True

        # 等待服务就绪
        start_time = time.time()
        url = f"http://{self.host}:{self.port}"
        while time.time() - start_time < timeout_sec:
            try:
                with socket.create_connection((self.host, self.port), timeout=0.5):
                    break
            except (OSError, ConnectionRefusedError):
                time.sleep(0.1)
        return url

    def stop(self):
        """安全停止 Flask 服务"""
        if self._is_running and self.server:
            try:
                self.server.shutdown()
            except Exception as e:
                logger.warning(f"关闭 Flask 服务异常: {e}")
            self._is_running = False


def is_kline_server_healthy(host: str = '127.0.0.1', port: int = 5000, timeout: float = 0.8) -> bool:
    """检查指定端口是否已存在正常运行的 KLinePlayground 后台服务"""
    import urllib.request
    import json
    url = f"http://{host}:{port}/api/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "KLineDesktopProbe/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                payload = json.loads(resp.read().decode('utf-8'))
                return payload.get('status') == 'ok'
    except Exception:
        return False
    return False


def launch_desktop(
    host: str = '127.0.0.1',
    port: Optional[int] = None,
    debug: bool = False,
    title: str = "K-Line Playground 复盘与看盘终端"
):
    """启动桌面端窗口与后台服务"""
    import webview

    storage_path = get_desktop_storage_path()
    icon_path = get_desktop_icon_path()

    server_mgr: Optional[DesktopServerManager] = None

    # 优先检测默认端口 (5000) 是否已有正在运行的 K-Line 后台服务
    if port is None and is_kline_server_healthy(host, 5000):
        app_url = f"http://{host}:5000"
        print("\n" + "=" * 66)
        print(f"  ★ K-Line Playground 桌面端已连接至正在运行的本地服务！")
        print(f"  ★ 服务地址: {app_url} (与 Web 浏览器共享同源及实时数据)")
        print(f"  ★ 数据持久化目录: {storage_path}")
        print("=" * 66 + "\n")
    else:
        server_mgr = DesktopServerManager(host=host, port=port)
        app_url = server_mgr.start()
        print("\n" + "=" * 66)
        print(f"  ★ K-Line Playground 桌面端已启动！")
        print(f"  ★ 桌面原生窗口: 正在唤起 (WebView2 Chromium 内核)...")
        print(f"  ★ 本地 Web 访问链接: {app_url} (外部浏览器亦可同步访问)")
        print(f"  ★ 数据持久化目录: {storage_path}")
        print("=" * 66 + "\n")

    # 创建独立窗口
    window = webview.create_window(
        title=title,
        url=app_url,
        width=1440,
        height=900,
        min_size=(1024, 600),
        text_select=True,
        confirm_close=False,
    )

    def on_window_closed():
        print("\n检测到桌面端窗口关闭...")
        if server_mgr:
            print("正在清理后台服务并退出...")
            server_mgr.stop()
        os._exit(0)

    window.events.closed += on_window_closed

    try:
        # private_mode=False 保证 localStorage、绘图与自选股在关闭后永久保存
        webview.start(
            debug=debug,
            private_mode=False,
            storage_path=storage_path,
            icon=icon_path
        )
    finally:
        if server_mgr:
            server_mgr.stop()


if __name__ == '__main__':
    launch_desktop()
