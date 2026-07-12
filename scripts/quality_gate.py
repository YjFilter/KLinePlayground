from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

PROFILE_COMMANDS: dict[str, list[list[str]]] = {
    "control-plane": [
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_agent_status.py", "-v"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_project_snapshot.py", "-v"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_quality_gate.py", "-v"],
        [sys.executable, "scripts/agent_status.py", ".agent/tasks"],
    ],
    "intraday": [
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_intraday_source.py", "-v"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_intraday_validator.py", "-v"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_intraday_validator_edge_cases.py", "-v"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_intraday_cache.py", "-v"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_intraday_service.py", "-v"],
    ],
    "phase2": [
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_intraday_aggregator.py", "-v"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_intraday_replay_clock.py", "-v"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_intraday_no_future_leakage.py", "-v"],
    ],
    "backend": [
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
    ],
    "frontend": [
        ["node", "--check", "frontend/js/main_enhanced.js"],
    ],
}


def _full_commands() -> list[list[str]]:
    commands: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for profile in ("control-plane", "intraday", "phase2", "backend", "frontend"):
        for command in PROFILE_COMMANDS[profile]:
            key = tuple(command)
            if key not in seen:
                seen.add(key)
                commands.append(command)
    return commands


PROFILE_COMMANDS["full"] = _full_commands()


def run_profile(profile: str, *, keep_going: bool = False, repo_root: Path = REPO_ROOT) -> int:
    commands = PROFILE_COMMANDS.get(profile)
    if commands is None:
        return 2
    first_failure = 0
    for command in commands:
        printable = subprocess.list2cmdline(command)
        print(f"[quality] RUN {printable}")
        started = time.perf_counter()
        completed = subprocess.run(command, cwd=repo_root, check=False)
        duration = time.perf_counter() - started
        if completed.returncode == 0:
            print(f"[quality] PASS {duration:.2f}s")
            continue
        print(f"[quality] FAIL exit={completed.returncode} {duration:.2f}s")
        if first_failure == 0:
            first_failure = completed.returncode or 1
        if not keep_going:
            break
    return first_failure


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a named KLinePlayground quality profile.")
    parser.add_argument("profile")
    parser.add_argument("--keep-going", action="store_true")
    args = parser.parse_args(argv)
    if args.profile not in PROFILE_COMMANDS:
        print(
            f"Unknown profile '{args.profile}'. Available: {', '.join(sorted(PROFILE_COMMANDS))}",
            file=sys.stderr,
        )
        return 2
    return run_profile(args.profile, keep_going=args.keep_going)


if __name__ == "__main__":
    sys.exit(main())
