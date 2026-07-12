from __future__ import annotations

import argparse
import sys
from pathlib import Path, PurePosixPath

TASK_STATES = {"backlog", "ready", "active", "review", "done", "blocked"}
REQUIRED_FIELDS = {"id", "title", "status", "priority", "owner", "write_scope", "quality_profiles"}


def _parse_scalar(value: str) -> object:
    value = value.strip()
    if value == "[]":
        return []
    if value.startswith("[") and value.endswith("]"):
        return [item.strip().strip("'\"") for item in value[1:-1].split(",") if item.strip()]
    return value.strip("'\"")


def parse_front_matter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    data: dict[str, object] = {}
    current_list: str | None = None
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            return data
        if stripped.startswith("- ") and current_list:
            value = stripped[2:].strip().strip("'\"")
            list_value = data.setdefault(current_list, [])
            if isinstance(list_value, list):
                list_value.append(value)
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value:
            data[key] = _parse_scalar(value)
            current_list = None
        else:
            data[key] = []
            current_list = key
    return {}


def _task_body(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def validate_task(path: Path, task_root: Path) -> list[str]:
    errors: list[str] = []
    data = parse_front_matter(path)
    missing = sorted(field for field in REQUIRED_FIELDS if field not in data)
    if missing:
        errors.append(f"{path}: missing required fields: {', '.join(missing)}")
        return errors

    declared_status = str(data["status"])
    directory_status = path.parent.name
    if declared_status not in TASK_STATES:
        errors.append(f"{path}: unsupported status '{declared_status}'")
    if directory_status != declared_status:
        errors.append(
            f"{path}: directory '{directory_status}' does not match declared status '{declared_status}'"
        )

    if declared_status in {"active", "review"} and str(data["owner"]).strip().lower() in {
        "",
        "unassigned",
        "none",
    }:
        errors.append(f"{path}: {declared_status} task requires an assigned owner")

    write_scope = data["write_scope"]
    if not isinstance(write_scope, list) or not write_scope:
        errors.append(f"{path}: write_scope must contain at least one path")
    quality_profiles = data["quality_profiles"]
    if not isinstance(quality_profiles, list) or not quality_profiles:
        errors.append(f"{path}: quality_profiles must contain at least one profile")
    if "## Acceptance Criteria" not in _task_body(path):
        errors.append(f"{path}: missing Acceptance Criteria section")
    return errors


def _normalized_scope(value: str) -> PurePosixPath:
    return PurePosixPath(value.replace("\\", "/").strip("/"))


def _paths_overlap(first: PurePosixPath, second: PurePosixPath) -> bool:
    return first == second or first in second.parents or second in first.parents


def find_write_scope_conflicts(task_root: Path) -> list[str]:
    owners: list[tuple[Path, PurePosixPath]] = []
    errors: list[str] = []
    active_dir = task_root / "active"
    if not active_dir.exists():
        return errors
    for path in sorted(active_dir.glob("*.md")):
        scopes = parse_front_matter(path).get("write_scope", [])
        if not isinstance(scopes, list):
            continue
        for scope in scopes:
            normalized = _normalized_scope(str(scope))
            for other_path, other_scope in owners:
                if _paths_overlap(normalized, other_scope):
                    errors.append(
                        f"write_scope overlap: {path} owns '{normalized}' and {other_path} owns '{other_scope}'"
                    )
            owners.append((path, normalized))
    return errors


def validate_repository(task_root: Path) -> list[str]:
    task_root = Path(task_root)
    errors: list[str] = []
    if not task_root.exists():
        return [f"task root does not exist: {task_root}"]
    for state in sorted(TASK_STATES):
        state_dir = task_root / state
        if not state_dir.exists():
            errors.append(f"missing task state directory: {state_dir}")
            continue
        for path in sorted(state_dir.glob("*.md")):
            errors.extend(validate_task(path, task_root))
    errors.extend(find_write_scope_conflicts(task_root))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate repository Agent task metadata.")
    parser.add_argument("task_root", nargs="?", default=".agent/tasks", type=Path)
    args = parser.parse_args(argv)
    errors = validate_repository(args.task_root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Agent task validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
