import tempfile
import unittest
from pathlib import Path


class AgentStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.task_root = Path(self.temp_dir.name) / "tasks"
        for state in ("backlog", "ready", "active", "review", "done", "blocked"):
            (self.task_root / state).mkdir(parents=True)

    def write_task(
        self,
        state: str,
        name: str,
        *,
        declared_status: str | None = None,
        owner: str = "unassigned",
        write_scope: tuple[str, ...] = ("example.txt",),
        acceptance: bool = True,
    ) -> Path:
        scope_lines = "\n".join(f"  - {path}" for path in write_scope)
        if acceptance:
            acceptance_section = "## Acceptance Criteria\n- [ ] Validator reports the expected result."
        else:
            acceptance_section = "## Notes\nNo acceptance contract."
        body = f"""---
id: TASK-001
title: Validate collaboration metadata
status: {declared_status or state}
priority: P2
owner: {owner}
depends_on: []
write_scope:
{scope_lines}
read_scope: []
quality_profiles:
  - control-plane
---

## Goal
Validate one repository task.

{acceptance_section}
"""
        path = self.task_root / state / name
        path.write_text(body, encoding="utf-8")
        return path

    def test_valid_ready_task_has_no_errors(self):
        from scripts.agent_status import validate_repository

        self.write_task("ready", "TASK-001-valid.md")

        self.assertEqual(validate_repository(self.task_root), [])

    def test_missing_owner_is_reported_for_active_task(self):
        from scripts.agent_status import validate_repository

        self.write_task("active", "TASK-001-active.md", owner="unassigned")

        errors = validate_repository(self.task_root)

        self.assertTrue(any("assigned owner" in error for error in errors))

    def test_directory_must_match_declared_status(self):
        from scripts.agent_status import validate_repository

        self.write_task("ready", "TASK-001-mismatch.md", declared_status="active", owner="codex")

        errors = validate_repository(self.task_root)

        self.assertTrue(any("directory" in error and "status" in error for error in errors))

    def test_overlapping_active_write_scope_is_reported(self):
        from scripts.agent_status import validate_repository

        self.write_task("active", "TASK-001-first.md", owner="worker-a", write_scope=("frontend/js",))
        self.write_task("active", "TASK-002-second.md", owner="worker-b", write_scope=("frontend/js/main_enhanced.js",))

        errors = validate_repository(self.task_root)

        self.assertTrue(any("overlap" in error for error in errors))

    def test_missing_acceptance_criteria_is_reported(self):
        from scripts.agent_status import validate_repository

        self.write_task("ready", "TASK-001-no-acceptance.md", acceptance=False)

        errors = validate_repository(self.task_root)

        self.assertTrue(any("Acceptance Criteria" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
