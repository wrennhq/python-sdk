from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx
import httpx_ws

from wrenn._git import Git
from wrenn.client import WrennClient
from wrenn.commands import Commands
from wrenn.files import Files
from wrenn.models import Capsule as CapsuleModel
from wrenn.models import Status, Template
from wrenn.pty import PtySession


def _build_proxy_url(base_url: str, capsule_id: str | None, port: int) -> str:
    parsed = httpx.URL(base_url)
    host = parsed.host
    if parsed.port:
        host = f"{host}:{parsed.port}"
    scheme = "ws" if parsed.scheme == "http" else "wss"
    return f"{scheme}://{port}-{capsule_id}.{host}"


class _DualMethod:
    """Descriptor that dispatches to instance method or classmethod depending on call site."""

    def __init__(self, instance_fn_name: str, static_fn_name: str) -> None:
        self._ifn = instance_fn_name
        self._sfn = static_fn_name

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    def __get__(self, obj: Any, cls: type) -> Any:
        if obj is None:
            return getattr(cls, self._sfn)
        return getattr(obj, self._ifn)


class Capsule:
    """A Wrenn capsule (sandbox) with e2b-compatible interface.

    Create directly::

        capsule = Capsule(api_key="wrn_...")
        capsule = Capsule(template="minimal")  # reads WRENN_API_KEY env

    Or via classmethod::

        capsule = Capsule.create(template="minimal")

    Use as context manager for automatic cleanup::

        with Capsule() as capsule:
            capsule.commands.run("echo hello")
    """

    def __init__(
        self,
        template: str | None = None,
        vcpus: int | None = None,
        memory_mb: int | None = None,
        timeout: int | None = None,
        *,
        wait: bool = False,
        api_key: str | None = None,
        base_url: str | None = None,
        # Private: used by classmethods to skip creation
        _capsule_id: str | None = None,
        _client: WrennClient | None = None,
        _info: CapsuleModel | None = None,
    ) -> None:
        """Create and start a new capsule.

        Args:
            template (str | None): Template name to boot from. Defaults to
                the server-side default (``"minimal"``).
            vcpus (int | None): Number of virtual CPUs. Defaults to the
                server-side default.
            memory_mb (int | None): Memory in MiB. Defaults to the
                server-side default.
            timeout (int | None): Inactivity TTL in seconds before the capsule
                is auto-paused. ``0`` disables auto-pause.
            wait (bool): If ``True``, block until the capsule status is
                ``running`` before returning.
            api_key (str | None): Wrenn API key (``wrn_...``). Falls back to
                the ``WRENN_API_KEY`` environment variable.
            base_url (str | None): Wrenn API base URL. Falls back to
                ``WRENN_BASE_URL`` or the default production endpoint.
        """
        if _capsule_id is not None:
            # Internal construction path (from create/connect classmethods)
            assert _client is not None
            self._id = _capsule_id
            self._client = _client
            self._info = _info
        else:
            # Public construction: create a capsule immediately
            self._client = WrennClient(api_key=api_key, base_url=base_url)
            self._info = self._client.capsules.create(
                template=template,
                vcpus=vcpus,
                memory_mb=memory_mb,
                timeout_sec=timeout,
            )
            self._id = self._info.id

        self.commands = Commands(self._id, self._client.http)
        self.files = Files(self._id, self._client.http)
        self.git = Git(self._id, self._client.http)

        if wait:
            self.wait_ready()

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
    def create(
        cls,
        template: str | None = None,
        vcpus: int | None = None,
        memory_mb: int | None = None,
        timeout: int | None = None,
        *,
        wait: bool = False,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> Capsule:
        """Create a new capsule.

        Equivalent to calling ``Capsule(...)`` directly.

        Args:
            template (str | None): Template name to boot from.
            vcpus (int | None): Number of virtual CPUs.
            memory_mb (int | None): Memory in MiB.
            timeout (int | None): Inactivity TTL in seconds before auto-pause.
            wait (bool): Block until the capsule reaches ``running`` status.
            api_key (str | None): Wrenn API key. Falls back to
                ``WRENN_API_KEY`` env var.
            base_url (str | None): API base URL override.

        Returns:
            Capsule: A new capsule instance.
        """
        return cls(
            template=template,
            vcpus=vcpus,
            memory_mb=memory_mb,
            timeout=timeout,
            wait=wait,
            api_key=api_key,
            base_url=base_url,
        )

    @classmethod
    def connect(
        cls,
        capsule_id: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> Capsule:
        """Connect to an existing capsule, resuming it if paused.

        Args:
            capsule_id (str): ID of the capsule to connect to.
            api_key (str | None): Wrenn API key. Falls back to
                ``WRENN_API_KEY`` env var.
            base_url (str | None): API base URL override.

        Returns:
            Capsule: A capsule instance bound to the existing capsule.

        Raises:
            WrennNotFoundError: If no capsule with the given ID exists.
        """
        client = WrennClient(api_key=api_key, base_url=base_url)
        info = client.capsules.get(capsule_id)

        if info.status == Status.paused:
            info = client.capsules.resume(capsule_id)

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

    def _instance_destroy(self) -> None:
        """Destroy this capsule."""
        self._client.capsules.destroy(self._id)

    @classmethod
    def _static_destroy(
        cls,
        capsule_id: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """Destroy a capsule by ID."""
        with WrennClient(api_key=api_key, base_url=base_url) as client:
            client.capsules.destroy(capsule_id)

    def _instance_pause(self) -> CapsuleModel:
        """Pause this capsule."""
        self._info = self._client.capsules.pause(self._id)
        return self._info

    @classmethod
    def _static_pause(
        cls,
        capsule_id: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> CapsuleModel:
        """Pause a capsule by ID."""
        with WrennClient(api_key=api_key, base_url=base_url) as client:
            return client.capsules.pause(capsule_id)

    def _instance_resume(self) -> CapsuleModel:
        """Resume this capsule."""
        self._info = self._client.capsules.resume(self._id)
        return self._info

    @classmethod
    def _static_resume(
        cls,
        capsule_id: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> CapsuleModel:
        """Resume a capsule by ID."""
        with WrennClient(api_key=api_key, base_url=base_url) as client:
            return client.capsules.resume(capsule_id)

    def _instance_get_info(self) -> CapsuleModel:
        """Get current info for this capsule."""
        self._info = self._client.capsules.get(self._id)
        return self._info

    @classmethod
    def _static_get_info(
        cls,
        capsule_id: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> CapsuleModel:
        """Get capsule info by ID."""
        with WrennClient(api_key=api_key, base_url=base_url) as client:
            return client.capsules.get(capsule_id)

    # ── Instance-only methods ───────────────────────────────────

    def ping(self) -> None:
        """Reset the capsule inactivity timer.

        Call this to prevent the capsule from being auto-paused when the
        inactivity TTL is set.
        """
        self._client.capsules.ping(self._id)

    def wait_ready(self, timeout: float = 30, interval: float = 0.5) -> None:
        """Block until the capsule status is ``running``.

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
            info = self._client.capsules.get(self._id)
            if info.status == Status.running:
                self._info = info
                return
            if info.status in (Status.error, Status.stopped, Status.paused):
                raise RuntimeError(f"Capsule entered {info.status} state while waiting")
            time.sleep(interval)
        raise TimeoutError(f"Capsule {self._id} did not become ready within {timeout}s")

    def is_running(self) -> bool:
        """Check whether the capsule is currently running.

        Makes a live API call to fetch current status.

        Returns:
            bool: ``True`` if the capsule status is ``running``.
        """
        info = self._instance_get_info()
        return info.status == Status.running

    # ── Static list ─────────────────────────────────────────────

    @classmethod
    def list(
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
        with WrennClient(api_key=api_key, base_url=base_url) as client:
            return client.capsules.list()

    # ── PTY ─────────────────────────────────────────────────────

    @contextmanager
    def pty(
        self,
        cmd: str = "/bin/bash",
        args: list[str] | None = None,
        cols: int = 80,
        rows: int = 24,
        envs: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> Iterator[PtySession]:
        """Open an interactive PTY session backed by a WebSocket.

        Use as a context manager and iterate over :class:`PtyEvent` objects::

            with capsule.pty() as term:
                term.write(b"echo hello\\n")
                for event in term:
                    if event.type == "output":
                        print(event.data.decode())

        Args:
            cmd (str): Command to run inside the PTY. Defaults to
                ``"/bin/bash"``.
            args (list[str] | None): Additional arguments for ``cmd``.
            cols (int): Initial terminal column count. Defaults to ``80``.
            rows (int): Initial terminal row count. Defaults to ``24``.
            envs (dict[str, str] | None): Additional environment variables to
                inject into the process.
            cwd (str | None): Working directory for the process.

        Yields:
            PtySession: An interactive PTY session.
        """
        with httpx_ws.connect_ws(
            f"/v1/capsules/{self._id}/pty", client=self._client.http
        ) as ws:
            session = PtySession(ws, self._id)
            session._send_start(
                cmd=cmd, args=args, cols=cols, rows=rows, envs=envs, cwd=cwd
            )
            yield session

    @contextmanager
    def pty_connect(self, tag: str) -> Iterator[PtySession]:
        """Reconnect to an existing PTY session by tag.

        Args:
            tag (str): Session tag returned in the ``started`` PTY event.

        Yields:
            PtySession: The reconnected PTY session.
        """
        with httpx_ws.connect_ws(
            f"/v1/capsules/{self._id}/pty", client=self._client.http
        ) as ws:
            session = PtySession(ws, self._id)
            session._send_connect(tag)
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

    def create_snapshot(
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
        return self._client.snapshots.create(
            capsule_id=self._id, name=name, overwrite=overwrite
        )

    # ── Context manager ─────────────────────────────────────────

    def __enter__(self) -> Capsule:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        try:
            self._instance_destroy()
        except Exception:
            pass
        try:
            self._client.close()
        except Exception:
            pass
