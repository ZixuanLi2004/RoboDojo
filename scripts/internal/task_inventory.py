#!/usr/bin/env python3
"""List benchmark tasks without importing Isaac-dependent task modules."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import sys
from typing import Any

from benchmark_profile import BENCHMARKS, ROOT_DIR


def _module_classes(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {node.name for node in tree.body if isinstance(node, ast.ClassDef)}


def _task_records(bench: str) -> list[dict[str, Any]]:
    task_dir = ROOT_DIR / "task" / bench / "tasks"
    config_dir = ROOT_DIR / "task" / bench / "config"
    records = []
    for path in sorted(task_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        name = path.stem
        classes = _module_classes(path)
        config_path = config_dir / f"{name}.yml"
        record = {
            "name": name,
            "variant": "language" if name.endswith("_l") else "spatial" if name.endswith("_s") else "standard",
            "module": str(path.relative_to(ROOT_DIR)),
            "class_name": name,
            "class_exists": name in classes,
            "config": str(config_path.relative_to(ROOT_DIR)) if config_path.exists() else None,
            "config_exists": config_path.exists(),
        }
        record["runnable"] = bool(record["class_exists"] and record["config_exists"])
        records.append(record)
    return records


def _inventory_counts(tasks: list[dict[str, Any]], config_only: list[str]) -> dict[str, int]:
    return {
        "tasks": len(tasks),
        "runnable": sum(1 for task in tasks if task["runnable"]),
        "missing_config": sum(1 for task in tasks if not task["config_exists"]),
        "missing_class": sum(1 for task in tasks if not task["class_exists"]),
        "config_only": len(config_only),
    }


def build_inventory(bench: str = "MobileArena") -> dict[str, Any]:
    if bench not in BENCHMARKS:
        raise ValueError(f"Unknown benchmark {bench!r}")
    task_dir = ROOT_DIR / "task" / bench / "tasks"
    config_dir = ROOT_DIR / "task" / bench / "config"
    tasks = _task_records(bench)
    task_names = {task["name"] for task in tasks}
    config_names = {path.stem for path in config_dir.glob("*.yml") if not path.name.startswith("_")}
    config_only = sorted(config_names - task_names)
    inventory = {
        "benchmark": bench,
        "root": str(ROOT_DIR),
        "task_dir": str(task_dir.relative_to(ROOT_DIR)),
        "config_dir": str(config_dir.relative_to(ROOT_DIR)),
        "counts": _inventory_counts(tasks, config_only),
        "tasks": tasks,
        "config_only": config_only,
    }
    return inventory


def _print_plain(inventory: dict[str, Any], only_runnable: bool) -> None:
    for task in inventory["tasks"]:
        if only_runnable and not task["runnable"]:
            continue
        print(task["name"])


def _print_markdown(inventory: dict[str, Any]) -> None:
    print("| Task | Variant | Runnable | Config | Issue |")
    print("| --- | --- | --- | --- | --- |")
    for task in inventory["tasks"]:
        issues = []
        if not task["class_exists"]:
            issues.append("missing exported class")
        if not task["config_exists"]:
            issues.append("missing config")
        print(
            f"| `{task['name']}` | {task['variant']} | "
            f"{'yes' if task['runnable'] else 'no'} | "
            f"`{task['config'] or '-'}` | {', '.join(issues) or '-'} |"
        )
    if inventory["config_only"]:
        print("\nConfig-only entries:")
        for name in inventory["config_only"]:
            print(f"- `{name}`")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", "--dataset", choices=tuple(BENCHMARKS), default="MobileArena")
    parser.add_argument(
        "--format",
        choices=("plain", "json", "markdown"),
        default="plain",
        help="Output format. Use json for agents and plain for shell loops.",
    )
    parser.add_argument(
        "--only-runnable",
        action="store_true",
        help="Only print runnable task names in plain output.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if any task is missing its config or exported class.",
    )
    args = parser.parse_args()

    inventory = build_inventory(args.bench)
    if args.format == "json":
        print(json.dumps(inventory, indent=2, sort_keys=True))
    elif args.format == "markdown":
        _print_markdown(inventory)
    else:
        _print_plain(inventory, only_runnable=args.only_runnable)

    if args.check:
        all_inventory = build_inventory(args.bench)
        errors = []
        for task in all_inventory["tasks"]:
            issues = []
            if not task["runnable"]:
                issues.append("not runnable")
            if issues:
                errors.append(f"Task {task['name']}: {', '.join(issues)}")
        errors.extend(f"Config {name} has no task module" for name in all_inventory["config_only"])
        if not all_inventory["tasks"]:
            errors.append(f"No {args.bench} task modules found")
        for error in errors:
            print(f"[ERROR] {error}", file=sys.stderr)
        if errors:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
