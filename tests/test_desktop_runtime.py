"""
Unit tests for KLinePlayground desktop runtime and dual-mode launcher.
Verifies port finding, server lifecycle, storage directories, and CLI entry points.
"""
from __future__ import annotations

import os
import sys
import socket
import unittest
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from desktop.desktop_app import (
    find_free_port,
    get_desktop_storage_path,
    get_desktop_icon_path,
    DesktopServerManager,
)


class DesktopRuntimeTest(unittest.TestCase):
    def test_find_free_port_basic(self):
        """Should find a valid bindable port starting from 5000."""
        port = find_free_port(start_port=5000, max_attempts=20)
        self.assertIsInstance(port, int)
        self.assertGreaterEqual(port, 5000)
        self.assertLess(port, 5020)

    def test_find_free_port_skips_occupied(self):
        """Should skip an occupied port and return the next free one."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occ:
            occ.bind(('127.0.0.1', 0))
            occ.listen(1)
            occupied_port = occ.getsockname()[1]

            next_port = find_free_port(start_port=occupied_port, max_attempts=10)
            self.assertNotEqual(next_port, occupied_port)
            self.assertGreater(next_port, occupied_port)

    def test_get_desktop_storage_path(self):
        """Should return existing persistent storage directory."""
        path = get_desktop_storage_path()
        self.assertTrue(os.path.isdir(path))
        self.assertIn('KLineStudio', path)

    def test_get_desktop_icon_path(self):
        """Should resolve a valid application icon."""
        icon = get_desktop_icon_path()
        self.assertIsNotNone(icon)
        self.assertTrue(os.path.isfile(icon))
        self.assertTrue(icon.endswith('.ico'))

    def test_desktop_server_manager_lifecycle(self):
        """Server manager should start background WSGI and cleanly shut down."""
        free_port = find_free_port(start_port=5200)
        mgr = DesktopServerManager(host='127.0.0.1', port=free_port)
        url = mgr.start(timeout_sec=5.0)
        self.assertEqual(url, f"http://127.0.0.1:{free_port}")

        try:
            # Probe health endpoint
            req = urllib.request.Request(f"{url}/api/health")
            with urllib.request.urlopen(req, timeout=3) as resp:
                self.assertEqual(resp.status, 200)
        finally:
            mgr.stop()

        # After stop, connection should be closed
        with self.assertRaises((OSError, ConnectionRefusedError)):
            with socket.create_connection(('127.0.0.1', free_port), timeout=0.5):
                pass

    def test_entry_files_exist(self):
        """Root scripts must exist for desktop and web."""
        self.assertTrue((PROJECT_ROOT / "run_desktop.py").is_file())
        self.assertTrue((PROJECT_ROOT / "run_web.py").is_file())
        self.assertTrue((PROJECT_ROOT / "main.py").is_file())
        self.assertTrue((PROJECT_ROOT / "scripts" / "create_desktop_shortcut.py").is_file())
        self.assertTrue((PROJECT_ROOT / "scripts" / "build_desktop.py").is_file())

    def test_is_kline_server_healthy(self):
        """Should detect running K-Line server via /api/health probe."""
        from desktop.desktop_app import is_kline_server_healthy
        # When server is not running on an unused port
        unused_port = find_free_port(start_port=5250)
        self.assertFalse(is_kline_server_healthy('127.0.0.1', unused_port, timeout=0.2))

        # Start a temporary server and probe
        mgr = DesktopServerManager(host='127.0.0.1', port=unused_port)
        mgr.start(timeout_sec=5.0)
        try:
            self.assertTrue(is_kline_server_healthy('127.0.0.1', unused_port, timeout=1.0))
        finally:
            mgr.stop()

    def test_state_sync_api_endpoints(self):
        """State sync API should return active user, account, watchlist and accept updates."""
        from backend.app_enhanced import app
        client = app.test_client()

        # 1. GET state
        res = client.get('/api/state/sync')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get('status'), 'ok')
        self.assertIn('active_user', data)
        self.assertIn('ashare_account', data)
        self.assertIn('ashare_watchlist', data)

        # 2. POST update active user & watchlist
        update_payload = {
            "active_user": "yj",
            "crypto_console_layout": {"collapsed": True}
        }
        post_res = client.post('/api/state/sync', json=update_payload)
        self.assertEqual(post_res.status_code, 200)
        post_data = post_res.get_json()
        self.assertEqual(post_data.get('status'), 'ok')

        # 3. GET verify persisted values
        verify_res = client.get('/api/state/sync')
        verify_data = verify_res.get_json()
        self.assertEqual(verify_data.get('active_user'), 'yj')
        self.assertEqual(verify_data.get('crypto_console_layout'), {"collapsed": True})


if __name__ == "__main__":
    unittest.main()
