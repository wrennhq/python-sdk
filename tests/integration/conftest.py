from __future__ import annotations

import os
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
import pytest_asyncio

from wrenn.async_capsule import AsyncCapsule
from wrenn.capsule import Capsule
from wrenn.client import AsyncWrennClient, WrennClient

WRENN_API_KEY = os.environ.get("WRENN_API_KEY")
WRENN_BASE_URL = os.environ.get("WRENN_BASE_URL", "http://localhost:8080")

_env_loaded = False


def _ensure_env() -> None:
    global _env_loaded
    if _env_loaded:
        return
    _env_loaded = True
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


@pytest.fixture(autouse=True)
def _load_env():
    _ensure_env()


def _has_auth() -> bool:
    return bool(WRENN_API_KEY)


requires_auth = pytest.mark.skipif(
    not _has_auth(),
    reason="Set WRENN_API_KEY to run integration tests",
)


@pytest.fixture
def client() -> Generator[WrennClient, None, None]:
    with WrennClient(
        api_key=WRENN_API_KEY,
        base_url=WRENN_BASE_URL,
    ) as c:
        yield c


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncWrennClient, None]:
    async with AsyncWrennClient(api_key=WRENN_API_KEY, base_url=WRENN_BASE_URL) as c:
        yield c


@pytest_asyncio.fixture
async def async_minimal_capsule() -> AsyncGenerator[AsyncCapsule, None]:
    """Provides a ready-to-use minimal capsule and cleans it up afterward."""
    async with await AsyncCapsule.create(
        template="minimal",
        timeout=120,
        wait=True,
        api_key=WRENN_API_KEY,
        base_url=WRENN_BASE_URL,
    ) as cap:
        yield cap


@pytest_asyncio.fixture
async def async_python_capsule() -> AsyncGenerator[AsyncCapsule, None]:
    """Provides a ready-to-use Python interpreter capsule."""
    async with await AsyncCapsule.create(
        template="python-interpreter-v0-beta",
        timeout=120,
        wait=True,
        api_key=WRENN_API_KEY,
        base_url=WRENN_BASE_URL,
    ) as cap:
        yield cap


@pytest.fixture
def minimal_capsule() -> Generator[Capsule, None, None]:
    """Provides a ready-to-use minimal capsule and cleans it up afterward."""
    with Capsule(
        template="minimal",
        timeout=120,
        wait=True,
        api_key=WRENN_API_KEY,
        base_url=WRENN_BASE_URL,
    ) as cap:
        yield cap
