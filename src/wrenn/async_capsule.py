from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx_ws

from wrenn.capsule import _DualMethod, _build_proxy_url
from wrenn.client import AsyncWrennClient
from wrenn.commands import AsyncCommands
from wrenn.files import AsyncFiles
from wrenn.models import Capsule as CapsuleModel
from wrenn.models import Status, Template
from wrenn.pty import AsyncPtySession


class AsyncCapsule:
    """Async Wrenn capsule with e2b-compatible interface.

    Create via classmethod::

        capsule = await AsyncCapsule.create(template="minimal")

    Use as async context manager::

        async with await AsyncCapsule.create() as capsule:
            await capsule.commands.run("echo hello")
    """

    def __init__(
        self,
        *,
        _capsule_id: str,
        _client: AsyncWrennClient,
        _info: CapsuleModel | None = None,
    ) -> None:
        self._id = _capsule_id
        self._client = _client
        self._info = _info

        self.commands = AsyncCommands(_capsule_id, _client.http)
        self.files = AsyncFiles(_capsule_id, _client.http)

    # ── Properties ──────────────────────────────────────────────

    @property
    def capsule_id(self) -> str:
        return self._id

    @property
    def info(self) -> CapsuleModel | None:
        return self._info

    # ── Factory classmethods ────────────────────────────────────

    @classmethod
    async def create(
        cls,
        template: str | None = None,
        vcpus: int | None = None,
        memory_mb: int | None = None,
        timeout: int | None = None,
        *,
        wait: bool = False,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> AsyncCapsule:
        """Create a new capsule."""
        client = AsyncWrennClient(api_key=api_key, base_url=base_url)
        info = await client.capsules.create(
            template=template,
            vcpus=vcpus,
            memory_mb=memory_mb,
            timeout_sec=timeout,
        )
        capsule = cls(
            _capsule_id=info.id,
            _client=client,
            _info=info,
        )
        if wait:
            await capsule.wait_ready()
        return capsule

    @classmethod
    async def connect(
        cls,
        capsule_id: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> AsyncCapsule:
        """Connect to an existing capsule. Resumes it if paused."""
        client = AsyncWrennClient(api_key=api_key, base_url=base_url)
        info = await client.capsules.get(capsule_id)

        if info.status == Status.paused:
            info = await client.capsules.resume(capsule_id)

        return cls(
            _capsule_id=capsule_id,
            _client=client,
            _info=info,
        )

    # ── Dual instance/static lifecycle ──────────────────────────

    destroy = _DualMethod("_instance_destroy", "_static_destroy")
    pause = _DualMethod("_instance_pause", "_static_pause")
    resume = _DualMethod("_instance_resume", "_static_resume")
    get_info = _DualMethod("_instance_get_info", "_static_get_info")

    async def _instance_destroy(self) -> None:
        await self._client.capsules.destroy(self._id)

    @classmethod
    async def _static_destroy(
        cls,
        capsule_id: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        async with AsyncWrennClient(api_key=api_key, base_url=base_url) as client:
            await client.capsules.destroy(capsule_id)

    async def _instance_pause(self) -> CapsuleModel:
        self._info = await self._client.capsules.pause(self._id)
        return self._info

    @classmethod
    async def _static_pause(
        cls,
        capsule_id: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> CapsuleModel:
        async with AsyncWrennClient(api_key=api_key, base_url=base_url) as client:
            return await client.capsules.pause(capsule_id)

    async def _instance_resume(self) -> CapsuleModel:
        self._info = await self._client.capsules.resume(self._id)
        return self._info

    @classmethod
    async def _static_resume(
        cls,
        capsule_id: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> CapsuleModel:
        async with AsyncWrennClient(api_key=api_key, base_url=base_url) as client:
            return await client.capsules.resume(capsule_id)

    async def _instance_get_info(self) -> CapsuleModel:
        self._info = await self._client.capsules.get(self._id)
        return self._info

    @classmethod
    async def _static_get_info(
        cls,
        capsule_id: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> CapsuleModel:
        async with AsyncWrennClient(api_key=api_key, base_url=base_url) as client:
            return await client.capsules.get(capsule_id)

    # ── Instance-only methods ───────────────────────────────────

    async def ping(self) -> None:
        await self._client.capsules.ping(self._id)

    async def wait_ready(self, timeout: float = 30, interval: float = 0.5) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            info = await self._client.capsules.get(self._id)
            if info.status == Status.running:
                self._info = info
                return
            if info.status in (Status.error, Status.stopped, Status.paused):
                raise RuntimeError(
                    f"Capsule entered {info.status} state while waiting"
                )
            await asyncio.sleep(interval)
        raise TimeoutError(
            f"Capsule {self._id} did not become ready within {timeout}s"
        )

    async def is_running(self) -> bool:
        info = await self._instance_get_info()
        return info.status == Status.running

    # ── Static list ─────────────────────────────────────────────

    @classmethod
    async def list(
        cls,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> list[CapsuleModel]:
        async with AsyncWrennClient(api_key=api_key, base_url=base_url) as client:
            return await client.capsules.list()

    # ── PTY ─────────────────────────────────────────────────────

    @asynccontextmanager
    async def pty(
        self,
        cmd: str = "/bin/bash",
        args: list[str] | None = None,
        cols: int = 80,
        rows: int = 24,
        envs: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> AsyncIterator[AsyncPtySession]:
        async with httpx_ws.aconnect_ws(
            f"/v1/capsules/{self._id}/pty", client=self._client.http
        ) as ws:
            session = AsyncPtySession(ws, self._id)
            await session._send_start(
                cmd=cmd, args=args, cols=cols, rows=rows, envs=envs, cwd=cwd
            )
            yield session

    @asynccontextmanager
    async def pty_connect(self, tag: str) -> AsyncIterator[AsyncPtySession]:
        async with httpx_ws.aconnect_ws(
            f"/v1/capsules/{self._id}/pty", client=self._client.http
        ) as ws:
            session = AsyncPtySession(ws, self._id)
            await session._send_connect(tag)
            yield session

    # ── Proxy helpers ───────────────────────────────────────────

    def get_url(self, port: int) -> str:
        return _build_proxy_url(self._client._base_url, self._id, port)

    # ── Snapshots ───────────────────────────────────────────────

    async def create_snapshot(
        self, name: str | None = None, overwrite: bool = False
    ) -> Template:
        return await self._client.snapshots.create(
            capsule_id=self._id, name=name, overwrite=overwrite
        )

    # ── Context manager ─────────────────────────────────────────

    async def __aenter__(self) -> AsyncCapsule:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        try:
            await self._instance_destroy()
        except Exception:
            pass
        try:
            await self._client.aclose()
        except Exception:
            pass
