from __future__ import annotations

import os
from pathlib import Path

import pytest

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def _read_env_file() -> dict[str, str]:
    result: dict[str, str] = {}
    if not ENV_FILE.exists():
        return result
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            result[key] = value
    return result


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    env_vars = _read_env_file()
    has_key = bool(os.environ.get("WRENN_API_KEY") or env_vars.get("WRENN_API_KEY"))
    if has_key:
        return
    skip = pytest.mark.skip(reason="WRENN_API_KEY not set")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
