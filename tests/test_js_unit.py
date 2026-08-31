"""Pytest gate for the frontend JS unit tests.

Runs every ``tests/js/*.test.js`` file through ``node --test`` so the pure
frontend modules (``frontend/js/modules/``) are covered by the standard
``pytest -q`` quality gate. Skipped when Node.js is not installed.
"""
from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JS_TEST_DIR = PROJECT_ROOT / "tests" / "js"


class JsUnitTestGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which("node")
        cls.test_files = sorted(JS_TEST_DIR.glob("*.test.js"))

    def test_all_js_unit_tests_pass(self):
        if not self.node:
            self.skipTest("node 未安装，跳过前端单测")
        self.assertTrue(self.test_files, f"未找到 JS 单测文件: {JS_TEST_DIR}")
        result = subprocess.run(
            [self.node, "--test", *[str(path) for path in self.test_files]],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"node --test 失败:\n{result.stdout[-4000:]}\n{result.stderr[-2000:]}",
        )
        self.assertIn("# fail 0", result.stdout)


if __name__ == "__main__":
    unittest.main()
