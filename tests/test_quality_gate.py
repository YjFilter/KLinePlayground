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
            "test_intraday_validator_edge_cases.py",
            "test_intraday_cache.py",
            "test_intraday_service.py",
        ):
            self.assertIn(filename, intraday_text)
        for command in intraday_commands:
            self.assertIn(command, full_commands)
            self.assertEqual(full_commands.count(command), 1)
    def test_phase2_profile_includes_clock_aggregation_and_leakage_tests(self):
        from scripts.quality_gate import PROFILE_COMMANDS

        phase2_commands = [tuple(command) for command in PROFILE_COMMANDS["phase2"]]
        phase2_text = "\n".join(" ".join(command) for command in PROFILE_COMMANDS["phase2"])
        full_commands = [tuple(command) for command in PROFILE_COMMANDS["full"]]

        for filename in (
            "test_intraday_aggregator.py",
            "test_intraday_replay_clock.py",
            "test_intraday_no_future_leakage.py",
        ):
            self.assertIn(filename, phase2_text)
        for command in phase2_commands:
            self.assertIn(command, full_commands)
            self.assertEqual(full_commands.count(command), 1)

    def test_phase3_profile_includes_trading_adaptation_tests(self):
        from scripts.quality_gate import PROFILE_COMMANDS

        phase3_commands = [tuple(command) for command in PROFILE_COMMANDS["phase3"]]
        phase3_text = "\n".join(" ".join(command) for command in PROFILE_COMMANDS["phase3"])
        full_commands = [tuple(command) for command in PROFILE_COMMANDS["full"]]

        for filename in (
            "test_intraday_trading_context.py",
            "test_intraday_advance_executor.py",
            "test_trade_timestamp_metadata.py",
            "test_intraday_trading_engine.py",
            "test_intraday_trading_equivalence.py",
        ):
            self.assertIn(filename, phase3_text)
        for command in phase3_commands:
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
