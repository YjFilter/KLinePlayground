from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from backend.crypto.history_prepare import (
    CryptoHistoryPrepareError,
    CryptoHistoryPrepareManager,
)


UTC = timezone.utc


class CryptoHistoryPrepareManagerTests(unittest.TestCase):
    def test_ready_job_reports_progress_and_is_consumed_once(self):
        updates = []

        def worker(user, payload, update, is_cancelled):
            self.assertEqual(user, "tester")
            self.assertEqual(payload["history_years"], 2)
            self.assertFalse(is_cancelled())
            update({"completed_chunks": 1, "total_chunks": 2, "current_start": "2024-01-01", "current_end": "2024-01-31"})
            updates.append("first")
            update({"completed_chunks": 2, "total_chunks": 2, "current_start": "2024-02-01", "current_end": "2024-02-29"})
            return {
                "token": "prepared-value",
                "summary": {"symbol": "BTCUSDT", "history_start": "2023-01-01 00:00:00"},
            }

        manager = CryptoHistoryPrepareManager(worker, runner=lambda callback: callback())
        created = manager.create("tester", {"history_years": 2})
        status = manager.get(created["job_id"], "tester")

        self.assertEqual(status["status"], "ready")
        self.assertEqual(status["completed_chunks"], 2)
        self.assertEqual(status["total_chunks"], 2)
        self.assertEqual(status["percent"], 100)
        self.assertEqual(status["symbol"], "BTCUSDT")
        self.assertEqual(updates, ["first"])
        self.assertEqual(manager.consume(created["job_id"], "tester")["token"], "prepared-value")
        with self.assertRaisesRegex(CryptoHistoryPrepareError, "already consumed"):
            manager.consume(created["job_id"], "tester")

    def test_job_is_private_to_its_user_and_can_be_cancelled(self):
        pending = []
        worker_called = []

        def worker(user, payload, update, is_cancelled):
            worker_called.append(True)
            return {"summary": {}}

        manager = CryptoHistoryPrepareManager(worker, runner=pending.append)
        created = manager.create("owner", {})

        with self.assertRaisesRegex(CryptoHistoryPrepareError, "not found"):
            manager.get(created["job_id"], "other")
        cancelled = manager.cancel(created["job_id"], "owner")
        pending.pop()()

        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(manager.get(created["job_id"], "owner")["status"], "cancelled")
        self.assertEqual(worker_called, [])

    def test_expired_job_is_removed(self):
        now = [datetime(2026, 7, 22, tzinfo=UTC)]
        manager = CryptoHistoryPrepareManager(
            lambda user, payload, update, is_cancelled: {"summary": {}},
            runner=lambda callback: callback(),
            ttl_seconds=60,
            now=lambda: now[0],
        )
        created = manager.create("tester", {})
        now[0] += timedelta(seconds=61)

        with self.assertRaisesRegex(CryptoHistoryPrepareError, "not found"):
            manager.get(created["job_id"], "tester")


if __name__ == "__main__":
    unittest.main()
