#!/usr/bin/env python3
"""Distribute MobileArena tasks across GPU workers by task count."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmark_profile import BENCHMARKS


def build_assignment(bench, env_cfg, task_names, policy_gpus, env_gpus):
    if bench not in BENCHMARKS:
        raise ValueError(f"Unknown benchmark: {bench}")
    if not policy_gpus or len(policy_gpus) != len(env_gpus):
        raise ValueError("Non-empty policy/env GPU lists must have equal lengths")
    groups = [[] for _ in policy_gpus]
    for index, task in enumerate(task_names):
        groups[index % len(groups)].append({"task": task})
    assignments = []
    for index, (policy_gpu, env_gpu, group) in enumerate(zip(policy_gpus, env_gpus, groups)):
        assignment = {
            "worker": index,
            "policy_gpu": policy_gpu,
            "env_gpu": env_gpu,
            "tasks": group,
            "load": f"{len(group)} tasks",
        }
        assignments.append(assignment)
    return {
        "benchmark": bench,
        "env_cfg": env_cfg,
        "weights_source": "task_count",
        "groups": assignments,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", choices=BENCHMARKS, required=True)
    parser.add_argument("--env-cfg", required=True)
    parser.add_argument("--tasks-file", type=Path, required=True)
    parser.add_argument("--policy-gpu-ids", required=True)
    parser.add_argument("--env-gpu-ids", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        tasks = [line.strip() for line in args.tasks_file.read_text().splitlines() if line.strip()]
        policy_gpus = args.policy_gpu_ids.split(",")
        env_gpus = args.env_gpu_ids.split(",")
        if any(not gpu.strip() for gpu in policy_gpus + env_gpus):
            raise ValueError("GPU ids must not be empty")
        assignment = build_assignment(args.bench, args.env_cfg, tasks, policy_gpus, env_gpus)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(assignment, indent=2) + "\n")
    print(json.dumps(assignment, indent=2))


if __name__ == "__main__":
    main()
