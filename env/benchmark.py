"""Benchmark-scoped paths shared by evaluation and scene loading."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from urllib.parse import quote, unquote

from env.global_configs import ASSETS_PATH, BENCHMARK, ROOT_DIR
from utils.benchmark_names import (
    benchmark_path_candidates,
    canonical_benchmark,
    canonical_profile,
    existing_benchmark_path,
)

_ENCODED_INFO_PREFIX = "urlencoded:"
_HASHED_INFO_PREFIX = "sha256:"


def encode_result_info(additional_info: str) -> str:
    """Keep checkpoint paths in one directory without changing model metadata.

    Ordinary run labels retain their existing paths. The marker distinguishes
    encoded paths from legacy labels containing literal percent escapes.
    """
    directory_info = additional_info
    if "/" in additional_info or "\\" in additional_info or additional_info.startswith(
        (_ENCODED_INFO_PREFIX, _HASHED_INFO_PREFIX)
    ):
        directory_info = _ENCODED_INFO_PREFIX + quote(additional_info, safe="=, ")
    # Leave room for the seed prefix within a filesystem's 255-byte component
    # limit. Keep the label reversible without adding result JSON metadata.
    if len(directory_info.encode("utf-8")) > 200:
        raise ValueError(
            "Encoded result label exceeds 200 bytes; use a shorter checkpoint name or path."
        )
    return directory_info


def decode_result_info(directory_info: str, result_path: str | Path | None = None) -> str:
    """Recover the original run label for display and checkpoint filtering."""
    if directory_info.startswith(_ENCODED_INFO_PREFIX):
        return unquote(directory_info[len(_ENCODED_INFO_PREFIX):])
    if directory_info.startswith(_HASHED_INFO_PREFIX):
        if result_path is None:
            raise ValueError("A hashed experiment label requires its result JSON metadata")
        payload = json.loads(Path(result_path).read_text(encoding="utf-8"))
        info = payload.get("additional_info") if isinstance(payload, dict) else None
        # Read older hashed results without generating new metadata-dependent labels.
        if not isinstance(info, str) or (
            _HASHED_INFO_PREFIX + hashlib.sha256(info.encode("utf-8")).hexdigest()
        ) != directory_info:
            raise ValueError("Result additional_info does not match its hashed experiment label")
        return info
    return directory_info


@dataclass(frozen=True)
class BenchmarkPaths:
    name: str = BENCHMARK

    def __post_init__(self):
        object.__setattr__(self, "name", canonical_benchmark(self.name))
        if self.name not in ("RoboDojo", "MobileArena"):
            raise ValueError(f"Unknown benchmark {self.name!r}; expected 'RoboDojo' or 'MobileArena'.")

    @classmethod
    def from_config(cls, config):
        """Read an eval profile, preserving the default for existing profiles."""
        return cls(config.get("benchmark", BENCHMARK))

    @property
    def task_dir(self) -> Path:
        return Path(ROOT_DIR, "task", self.name)

    @property
    def config_dir(self) -> Path:
        return self.task_dir / "config"

    @property
    def objects_dir(self) -> Path:
        return existing_benchmark_path(ASSETS_PATH, "Object", self.name)

    def layout_dir(self, config_name, seed) -> Path:
        return existing_benchmark_path(ASSETS_PATH, "Eval_Layout", self.name, config_name, seed)

    def result_dir(self, eval_cfg) -> Path:
        """Parent of timestamped results and the associated resume manifest."""
        return Path(
            "eval_result",
            self.name,
            eval_cfg["task_name"],
            eval_cfg["policy_name"],
            canonical_profile(eval_cfg["config_name"]) if self.name == "MobileArena" else eval_cfg["config_name"],
            f"{eval_cfg.get('seed', 0)}_{encode_result_info(eval_cfg.get('additional_info', ''))}",
        )

    def resume_manifest_path(self, eval_cfg, run_id) -> Path:
        result = self.result_dir(eval_cfg)
        if self.name != "MobileArena":
            return result / f"_resume_{run_id}.json"
        # An interrupted legacy run keeps its original manifest and save_dir.
        for prefix in benchmark_path_candidates("eval_result", self.name):
            for config in benchmark_path_candidates("", eval_cfg["config_name"]):
                candidate = (
                    prefix / eval_cfg["task_name"] / eval_cfg["policy_name"]
                    / config / result.name / f"_resume_{run_id}.json"
                )
                if candidate.is_file():
                    return candidate
        return result / f"_resume_{run_id}.json"

    def resumed_result_dir(self, eval_cfg, run_id) -> Path:
        """Let batch completion checks follow the same save_dir as the client."""
        try:
            manifest = json.loads(self.resume_manifest_path(eval_cfg, run_id).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            manifest = None
        if isinstance(manifest, dict) and isinstance(manifest.get("save_dir"), str) and manifest["save_dir"]:
            return Path(manifest["save_dir"])
        return self.result_dir(eval_cfg) / run_id
