import unittest
from types import SimpleNamespace
from unittest.mock import patch


class QualityGateTests(unittest.TestCase):
    def test_unknown_profile_returns_usage_error(self):
        from scripts.quality_gate import main

        self.assertEqual(main(["missing-profile"]), 2)

    def test_control_plane_profile_runs_expected_commands(self):
        from scripts.quality_gate import PROFILE_COMMANDS, run_profile

        completed = SimpleNamespace(returncode=0)
        with patch("scripts.quality_gate.subprocess.run", return_value=completed) as runner:
            result = run_profile("control-plane")

        self.assertEqual(result, 0)
        self.assertEqual(runner.call_count, len(PROFILE_COMMANDS["control-plane"]))

    def test_control_plane_profile_includes_all_control_plane_test_files(self):
        from scripts.quality_gate import PROFILE_COMMANDS

        command_text = "\n".join(" ".join(command) for command in PROFILE_COMMANDS["control-plane"])

        self.assertIn("test_agent_status.py", command_text)
        self.assertIn("test_project_snapshot.py", command_text)
        self.assertIn("test_quality_gate.py", command_text)
    def test_intraday_profile_includes_all_intraday_test_files_and_full_reuses_them(self):
        from scripts.quality_gate import PROFILE_COMMANDS

        intraday_commands = [tuple(command) for command in PROFILE_COMMANDS["intraday"]]
        intraday_text = "\n".join(" ".join(command) for command in PROFILE_COMMANDS["intraday"])
        full_commands = [tuple(command) for command in PROFILE_COMMANDS["full"]]

        for filename in (
            "test_intraday_source.py",
            "test_intraday_validator.py",
            "test_intraday_cache.py",
            "test_intraday_service.py",
        ):
            self.assertIn(filename, intraday_text)
        for command in intraday_commands:
            self.assertIn(command, full_commands)
            self.assertEqual(full_commands.count(command), 1)
    def test_first_failure_produces_nonzero_exit(self):
        from scripts.quality_gate import run_profile

        results = [SimpleNamespace(returncode=3), SimpleNamespace(returncode=0)]
        with patch("scripts.quality_gate.subprocess.run", side_effect=results) as runner:
            result = run_profile("control-plane")

        self.assertEqual(result, 3)
        self.assertEqual(runner.call_count, 1)

    def test_keep_going_runs_remaining_commands(self):
        from scripts.quality_gate import PROFILE_COMMANDS, run_profile

        results = [SimpleNamespace(returncode=1)] + [
            SimpleNamespace(returncode=0) for _ in PROFILE_COMMANDS["control-plane"][1:]
        ]
        with patch("scripts.quality_gate.subprocess.run", side_effect=results) as runner:
            result = run_profile("control-plane", keep_going=True)

        self.assertEqual(result, 1)
        self.assertEqual(runner.call_count, len(PROFILE_COMMANDS["control-plane"]))


if __name__ == "__main__":
    unittest.main()
