"""Resolve benchmark names and paths using the shared environment constants."""

from itertools import product
from pathlib import Path

from env.global_configs import BENCHMARK_NAME_ALIASES, PROFILE_NAME_ALIASES

_ALIASES = {"benchmark": BENCHMARK_NAME_ALIASES, "profile": PROFILE_NAME_ALIASES}


def canonical_benchmark(name: str) -> str:
    return _ALIASES["benchmark"].get(name, name)


def canonical_profile(name: str) -> str:
    return _ALIASES["profile"].get(name, name)


def benchmark_path_candidates(root, *parts) -> list[Path]:
    """Prefer current names, then legacy storage names; never alter user labels."""
    alternatives = []
    for part in map(str, parts):
        for aliases in _ALIASES.values():
            canonical = aliases.get(part, part)
            legacy = tuple(alias for alias, target in aliases.items() if target == canonical)
            if legacy:
                alternatives.append((canonical, *legacy))
                break
        else:
            alternatives.append((part,))
    return [Path(root, *names) for names in product(*alternatives)]


def existing_benchmark_path(root, *parts) -> Path:
    """Read existing assets without moving shared files or rewriting USD links."""
    candidates = benchmark_path_candidates(root, *parts)
    return next((path for path in candidates if path.exists()), candidates[0])


def room_asset_path(assets_root, category) -> Path:
    return existing_benchmark_path(assets_root, "Room", *Path(category).parts)
