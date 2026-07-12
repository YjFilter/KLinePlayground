import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


class ProjectSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.repo_root = Path(self.temp_dir.name)
        agent_root = self.repo_root / ".agent"
        (agent_root / "handoffs").mkdir(parents=True)
        for state in ("backlog", "ready", "active", "review", "done", "blocked"):
            (agent_root / "tasks" / state).mkdir(parents=True)
        (agent_root / "STATE.md").write_text(
            "# Current Project State\n\n## Active Milestone\nM1 - Agent Control Plane\n\n## Next Action\nValidate one task.\n",
            encoding="utf-8",
        )
        (agent_root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (agent_root / "ARCHITECTURE.md").write_text("# Architecture\n", encoding="utf-8")
        (agent_root / "handoffs" / "2026-07-12-latest.md").write_text("# Latest Handoff\n", encoding="utf-8")
        (agent_root / "tasks" / "ready" / "TASK-001.md").write_text("# Task\n", encoding="utf-8")

    def test_snapshot_contains_state_task_counts_handoff_and_git_summary(self):
        from scripts.project_snapshot import build_snapshot

        completed = SimpleNamespace(stdout="## master...origin/master\n?? .agent/\n", returncode=0)
        with patch("scripts.project_snapshot.subprocess.run", return_value=completed):
            snapshot = build_snapshot(self.repo_root)

        self.assertIn("M1 - Agent Control Plane", snapshot)
        self.assertIn("Validate one task.", snapshot)
        self.assertIn("ready: 1", snapshot)
        self.assertIn("active: 0", snapshot)
        self.assertIn("2026-07-12-latest.md", snapshot)
        self.assertIn("master...origin/master", snapshot)

    def test_latest_handoff_uses_newest_filename(self):
        from scripts.project_snapshot import latest_handoff

        handoff_root = self.repo_root / ".agent" / "handoffs"
        (handoff_root / "2026-07-11-older.md").write_text("older", encoding="utf-8")

        self.assertEqual(latest_handoff(handoff_root).name, "2026-07-12-latest.md")


if __name__ == "__main__":
    unittest.main()
