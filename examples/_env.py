import os
from pathlib import Path


def _load_file(path: Path, *, original_env_keys: set[str], override: bool) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        normalized_key = key.strip()
        normalized_value = value.strip()

        if normalized_key in original_env_keys:
            continue

        if override or normalized_key not in os.environ:
            os.environ[normalized_key] = normalized_value


def load_env() -> None:
    root = Path(__file__).resolve().parents[1]
    original_env_keys = set(os.environ.keys())

    _load_file(
        root / ".env.example",
        original_env_keys=original_env_keys,
        override=False,
    )
    _load_file(
        root / ".env",
        original_env_keys=original_env_keys,
        override=True,
    )
