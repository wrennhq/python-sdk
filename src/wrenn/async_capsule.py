from __future__ import annotations

import asyncio
import logging
import builtins
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx_ws

from wrenn._git import AsyncGit
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
        self.git = AsyncGit(_capsule_id, _client.http)

    # ── Properties ──────────────────────────────────────────────

    @property
    def capsule_id(self) -> str:
        """The capsule's unique identifier.

        Returns:
            str: Capsule ID assigned by the Wrenn API.
        """
        return self._id

    @property
    def info(self) -> CapsuleModel | None:
        """Cached capsule metadata from the last API call.

        Returns:
            CapsuleModel | None: The last-fetched capsule model, or ``None``
            if the capsule was connected without an initial fetch.
        """
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
        """Create a new capsule.

        Args:
            template (str | None): Template name to boot from.
            vcpus (int | None): Number of virtual CPUs.
            memory_mb (int | None): Memory in MiB.
            timeout (int | None): Inactivity TTL in seconds before auto-pause.
            wait (bool): Await until the capsule reaches ``running`` status.
            api_key (str | None): Wrenn API key. Falls back to
                ``WRENN_API_KEY`` env var.
            base_url (str | None): API base URL override.

        Returns:
            AsyncCapsule: A new capsule instance.
        """
        client = AsyncWrennClient(api_key=api_key, base_url=base_url)
        info = await client.capsules.create(
            template=template,
            vcpus=vcpus,
            memory_mb=memory_mb,
            timeout_sec=timeout,
        )
        assert info.id is not None
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
        """Connect to an existing capsule, resuming it if paused.

        Args:
            capsule_id (str): ID of the capsule to connect to.
            api_key (str | None): Wrenn API key. Falls back to
                ``WRENN_API_KEY`` env var.
            base_url (str | None): API base URL override.

        Returns:
            AsyncCapsule: A capsule instance bound to the existing capsule.

        Raises:
            WrennNotFoundError: If no capsule with the given ID exists.
        """
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
        """Reset the capsule inactivity timer.

        Call this to prevent the capsule from being auto-paused when the
        inactivity TTL is set.
        """
        await self._client.capsules.ping(self._id)

    async def wait_ready(self, timeout: float = 30, interval: float = 0.5) -> None:
        """Await until the capsule status is ``running``.

        Args:
            timeout (float): Maximum seconds to wait. Defaults to ``30``.
            interval (float): Polling interval in seconds. Defaults to ``0.5``.

        Raises:
            TimeoutError: If the capsule does not reach ``running`` state
                within ``timeout`` seconds.
            RuntimeError: If the capsule enters an error, stopped, or paused
                state while waiting.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            info = await self._client.capsules.get(self._id)
            if info.status == Status.running:
                self._info = info
                return
            if info.status in (Status.error, Status.stopped):
                raise RuntimeError(f"Capsule entered {info.status} state while waiting")
            if info.status == Status.paused:
                info = await self._client.capsules.resume(self._id)
            await asyncio.sleep(interval)
        raise TimeoutError(f"Capsule {self._id} did not become ready within {timeout}s")

    async def is_running(self) -> bool:
        """Check whether the capsule is currently running.

        Makes a live API call to fetch current status.

        Returns:
            bool: ``True`` if the capsule status is ``running``.
        """
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
        """List all capsules belonging to the team.

        Args:
            api_key (str | None): Wrenn API key. Falls back to
                ``WRENN_API_KEY`` env var.
            base_url (str | None): API base URL override.

        Returns:
            list[CapsuleModel]: All capsules for the authenticated team.
        """
        async with AsyncWrennClient(api_key=api_key, base_url=base_url) as client:
            return await client.capsules.list()

    # ── PTY ─────────────────────────────────────────────────────

    @asynccontextmanager
    async def pty(
        self,
        cmd: str = "/bin/bash",
        args: builtins.list[str] | None = None,
        cols: int = 80,
        rows: int = 24,
        envs: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> AsyncIterator[AsyncPtySession]:
        """Open an async interactive PTY session backed by a WebSocket.

        Use as an async context manager and async iterate over
        :class:`PtyEvent` objects::

            async with capsule.pty() as term:
                await term.write(b"echo hello\\n")
                async for event in term:
                    if event.type == "output":
                        print(event.data.decode())

        Args:
            cmd (str): Command to run inside the PTY. Defaults to
                ``"/bin/bash"``.
            args (list[str] | None): Additional arguments for ``cmd``.
            cols (int): Initial terminal column count. Defaults to ``80``.
            rows (int): Initial terminal row count. Defaults to ``24``.
            envs (dict[str, str] | None): Additional environment variables
                to inject into the process.
            cwd (str | None): Working directory for the process.

        Yields:
            AsyncPtySession: An interactive async PTY session.
        """
        async with httpx_ws.aconnect_ws(
            f"/v1/capsules/{self._id}/pty", client=self._client.http
        ) as ws:  # type: httpx_ws.AsyncWebSocketSession
            session = AsyncPtySession(ws, self._id)
            await session._send_start(
                cmd=cmd, args=args, cols=cols, rows=rows, envs=envs, cwd=cwd
            )
            yield session

    @asynccontextmanager
    async def pty_connect(self, tag: str) -> AsyncIterator[AsyncPtySession]:
        """Reconnect to an existing PTY session by tag.

        Args:
            tag (str): Session tag returned in the ``started`` PTY event.

        Yields:
            AsyncPtySession: The reconnected async PTY session.
        """
        async with httpx_ws.aconnect_ws(
            f"/v1/capsules/{self._id}/pty", client=self._client.http
        ) as ws:  # type: httpx_ws.AsyncWebSocketSession
            session = AsyncPtySession(ws, self._id)
            await session._send_connect(tag)
            yield session

    # ── Proxy helpers ───────────────────────────────────────────

    def get_url(self, port: int) -> str:
        """Get the proxy URL for a port exposed inside this capsule.

        Args:
            port (int): Port number to proxy.

        Returns:
            str: A ``wss://`` (or ``ws://``) URL that proxies to the given
            port inside the capsule.
        """
        return _build_proxy_url(self._client._base_url, self._id, port)

    # ── Snapshots ───────────────────────────────────────────────

    async def create_snapshot(
        self, name: str | None = None, overwrite: bool = False
    ) -> Template:
        """Create a snapshot template from this capsule's current state.

        Args:
            name (str | None): Name for the snapshot template. Auto-generated
                if not provided.
            overwrite (bool): If ``True``, overwrite an existing template with
                the same name. Defaults to ``False``.

        Returns:
            Template: The created snapshot template.
        """
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
        except Exception as exc:
            logging.warning("Failed to destroy capsule %s: %s", self._id, exc)
        try:
            await self._client.aclose()
        except Exception:
            pass
