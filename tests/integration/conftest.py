from __future__ import annotations

import os
from typing import Generator

import pytest
import pytest_asyncio
from typing_extensions import AsyncGenerator

from wrenn.capsule import Capsule
from wrenn.client import AsyncWrennClient, WrennClient

WRENN_API_KEY = os.environ.get("WRENN_API_KEY")
WRENN_TOKEN = os.environ.get("WRENN_TOKEN")
WRENN_BASE_URL = os.environ.get("WRENN_BASE_URL", "http://localhost:8080")
WRENN_TEST_EMAIL = os.environ.get("WRENN_TEST_EMAIL")
WRENN_TEST_PASSWORD = os.environ.get("WRENN_TEST_PASSWORD")


def _has_auth() -> bool:
    return bool(WRENN_API_KEY or WRENN_TOKEN)


requires_auth = pytest.mark.skipif(
    not _has_auth(),
    reason="Set WRENN_API_KEY or WRENN_TOKEN to run integration tests",
)


@pytest.fixture
def client() -> Generator[WrennClient, None, None]:
    with WrennClient(
        api_key=WRENN_API_KEY,
        token=WRENN_TOKEN,
        base_url=WRENN_BASE_URL,
    ) as c:
        yield c


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncWrennClient, None]:
    async with AsyncWrennClient(
        api_key=WRENN_API_KEY, token=WRENN_TOKEN, base_url=WRENN_BASE_URL
    ) as c:
        yield c


@pytest.fixture
def bearer_client() -> Generator[WrennClient, None, None]:
    if WRENN_TOKEN:
        with WrennClient(token=WRENN_TOKEN, base_url=WRENN_BASE_URL) as c:
            yield c
    elif WRENN_TEST_EMAIL and WRENN_TEST_PASSWORD:
        with WrennClient(api_key=WRENN_API_KEY, base_url=WRENN_BASE_URL) as c:
            resp = c.auth.login(WRENN_TEST_EMAIL, WRENN_TEST_PASSWORD)
        with WrennClient(token=resp.token, base_url=WRENN_BASE_URL) as c:
            yield c
    else:
        pytest.skip(
            "Set WRENN_TOKEN or WRENN_TEST_EMAIL+WRENN_TEST_PASSWORD for bearer-auth tests"
        )


@pytest_asyncio.fixture
async def async_minimal_capsule(
    async_client: AsyncWrennClient,
) -> AsyncGenerator[Capsule, None]:
    """Provides a ready-to-use minimal capsule and cleans it up afterward."""
    cap = await async_client.capsules.create(template="minimal", timeout_sec=120)
    await cap.async_wait_ready(timeout=60, interval=1)
    yield cap
    await cap.async_destroy()


@pytest_asyncio.fixture
async def async_python_capsule(
    async_client: AsyncWrennClient,
) -> AsyncGenerator[Capsule, None]:
    """Provides a ready-to-use Python interpreter capsule."""
    cap = await async_client.capsules.create(
        template="python-interpreter-v0-beta", timeout_sec=120
    )
    await cap.async_wait_ready(timeout=60, interval=1)
    yield cap
    await cap.async_destroy()


@pytest.fixture
def minimal_capsule(
    client: WrennClient,
) -> Generator[Capsule, None, None]:
    """Provides a ready-to-use minimal capsule and cleans it up afterward."""
    with client.capsules.create(template="minimal", timeout_sec=120) as cap:
        cap.wait_ready(timeout=60, interval=1)
        yield cap
