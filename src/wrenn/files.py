from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import httpx

from wrenn.exceptions import WrennNotFoundError, _raise_for_status, handle_response
from wrenn.models import FileEntry, ListDirResponse, MakeDirResponse


class Files:
    """Sync filesystem interface. Accessed via ``capsule.files``."""

    def __init__(self, capsule_id: str, http: httpx.Client) -> None:
        self._capsule_id = capsule_id
        self._http = http

    def read(self, path: str) -> str:
        """Read a file as a UTF-8 string.

        Args:
            path (str): Absolute path to the file inside the capsule.

        Returns:
            str: File contents decoded as UTF-8.

        Raises:
            WrennNotFoundError: If the path does not exist.
        """
        return self.read_bytes(path).decode("utf-8", errors="replace")

    def read_bytes(self, path: str) -> bytes:
        """Read a file as raw bytes.

        Args:
            path (str): Absolute path to the file inside the capsule.

        Returns:
            bytes: Raw file contents.

        Raises:
            WrennNotFoundError: If the path does not exist.
        """
        resp = self._http.post(
            f"/v1/capsules/{self._capsule_id}/files/read",
            json={"path": path},
        )
        _raise_for_status(resp)
        return resp.content

    def write(self, path: str, data: str | bytes) -> None:
        """Write data to a file inside the capsule.

        Creates parent directories if they do not exist.

        Args:
            path (str): Absolute destination path inside the capsule.
            data (str | bytes): Content to write. Strings are UTF-8 encoded.
        """
        if isinstance(data, str):
            data = data.encode("utf-8")
        resp = self._http.post(
            f"/v1/capsules/{self._capsule_id}/files/write",
            files={"file": ("upload", data)},
            data={"path": path},
        )
        _raise_for_status(resp)

    def list(self, path: str, depth: int = 1) -> list[FileEntry]:
        """List directory contents.

        Args:
            path (str): Absolute path to the directory inside the capsule.
            depth (int): Recursion depth. ``1`` lists only immediate children.
                Defaults to ``1``.

        Returns:
            list[FileEntry]: Entries in the directory.

        Raises:
            WrennNotFoundError: If the path does not exist.
        """
        resp = self._http.post(
            f"/v1/capsules/{self._capsule_id}/files/list",
            json={"path": path, "depth": depth},
        )
        parsed = ListDirResponse.model_validate(handle_response(resp))
        return parsed.entries or []

    def exists(self, path: str) -> bool:
        """Check whether a path exists inside the capsule.

        Args:
            path (str): Absolute path to check.

        Returns:
            bool: ``True`` if the path exists.
        """
        parent = os.path.dirname(path)
        name = os.path.basename(path)
        try:
            entries = self.list(parent, depth=1)
        except WrennNotFoundError:
            return False
        return any(e.name == name for e in entries)

    def make_dir(self, path: str) -> FileEntry:
        """Create a directory (with parents). Idempotent.

        Args:
            path (str): Absolute path of the directory to create.

        Returns:
            FileEntry: The created (or already-existing) directory entry.
        """
        resp = self._http.post(
            f"/v1/capsules/{self._capsule_id}/files/mkdir",
            json={"path": path},
        )
        if resp.status_code == 409:
            try:
                body = resp.json()
                if body.get("error", {}).get("code") == "conflict":
                    parent = os.path.dirname(path)
                    name = os.path.basename(path)
                    for entry in self.list(parent, depth=1):
                        if entry.name == name:
                            return entry
            except Exception:
                pass
        parsed = MakeDirResponse.model_validate(handle_response(resp))
        if parsed.entry is None:
            raise RuntimeError("mkdir response missing entry")
        return parsed.entry

    def remove(self, path: str) -> None:
        """Remove a file or directory recursively.

        Args:
            path (str): Absolute path to remove.

        Raises:
            WrennNotFoundError: If the path does not exist.
        """
        resp = self._http.post(
            f"/v1/capsules/{self._capsule_id}/files/remove",
            json={"path": path},
        )
        handle_response(resp)

    def upload_stream(self, path: str, stream: Iterator[bytes]) -> None:
        """Stream a large file into the capsule.

        Prefer this over :meth:`write` when the file is too large to hold in
        memory.

        Args:
            path (str): Absolute destination path inside the capsule.
            stream (Iterator[bytes]): Iterable of byte chunks to upload.
        """
        boundary = os.urandom(16).hex().encode("utf-8")

        def _multipart() -> Iterator[bytes]:
            yield b"--" + boundary + b"\r\n"
            yield b'Content-Disposition: form-data; name="path"\r\n\r\n'
            yield path.encode("utf-8") + b"\r\n"
            yield b"--" + boundary + b"\r\n"
            yield b'Content-Disposition: form-data; name="file"; filename="upload.bin"\r\n'
            yield b"Content-Type: application/octet-stream\r\n\r\n"
            for chunk in stream:
                yield chunk if isinstance(chunk, bytes) else chunk.encode("utf-8")
            yield b"\r\n--" + boundary + b"--\r\n"

        resp = self._http.post(
            f"/v1/capsules/{self._capsule_id}/files/stream/write",
            content=_multipart(),
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary.decode('utf-8')}"
            },
        )
        _raise_for_status(resp)

    def download_stream(self, path: str) -> Iterator[bytes]:
        """Stream a large file out of the capsule.

        Prefer this over :meth:`read_bytes` when the file is too large to hold
        in memory.

        Args:
            path (str): Absolute path to the file inside the capsule.

        Yields:
            bytes: Successive byte chunks of the file.

        Raises:
            WrennNotFoundError: If the path does not exist.
        """
        with self._http.stream(
            "POST",
            f"/v1/capsules/{self._capsule_id}/files/stream/read",
            json={"path": path},
        ) as resp:
            resp.raise_for_status()
            yield from resp.iter_bytes()


class AsyncFiles:
    """Async filesystem interface. Accessed via ``capsule.files``."""

    def __init__(self, capsule_id: str, http: httpx.AsyncClient) -> None:
        self._capsule_id = capsule_id
        self._http = http

    async def read(self, path: str) -> str:
        """Read a file as a UTF-8 string.

        Args:
            path (str): Absolute path to the file inside the capsule.

        Returns:
            str: File contents decoded as UTF-8.

        Raises:
            WrennNotFoundError: If the path does not exist.
        """
        data = await self.read_bytes(path)
        return data.decode("utf-8", errors="replace")

    async def read_bytes(self, path: str) -> bytes:
        """Read a file as raw bytes.

        Args:
            path (str): Absolute path to the file inside the capsule.

        Returns:
            bytes: Raw file contents.

        Raises:
            WrennNotFoundError: If the path does not exist.
        """
        resp = await self._http.post(
            f"/v1/capsules/{self._capsule_id}/files/read",
            json={"path": path},
        )
        _raise_for_status(resp)
        return resp.content

    async def write(self, path: str, data: str | bytes) -> None:
        """Write data to a file inside the capsule.

        Creates parent directories if they do not exist.

        Args:
            path (str): Absolute destination path inside the capsule.
            data (str | bytes): Content to write. Strings are UTF-8 encoded.
        """
        if isinstance(data, str):
            data = data.encode("utf-8")
        resp = await self._http.post(
            f"/v1/capsules/{self._capsule_id}/files/write",
            files={"file": ("upload", data)},
            data={"path": path},
        )
        _raise_for_status(resp)

    async def list(self, path: str, depth: int = 1) -> list[FileEntry]:
        """List directory contents.

        Args:
            path (str): Absolute path to the directory inside the capsule.
            depth (int): Recursion depth. ``1`` lists only immediate children.
                Defaults to ``1``.

        Returns:
            list[FileEntry]: Entries in the directory.

        Raises:
            WrennNotFoundError: If the path does not exist.
        """
        resp = await self._http.post(
            f"/v1/capsules/{self._capsule_id}/files/list",
            json={"path": path, "depth": depth},
        )
        parsed = ListDirResponse.model_validate(handle_response(resp))
        return parsed.entries or []

    async def exists(self, path: str) -> bool:
        """Check whether a path exists inside the capsule.

        Args:
            path (str): Absolute path to check.

        Returns:
            bool: ``True`` if the path exists.
        """
        parent = os.path.dirname(path)
        name = os.path.basename(path)
        try:
            entries = await self.list(parent, depth=1)
        except WrennNotFoundError:
            return False
        return any(e.name == name for e in entries)

    async def make_dir(self, path: str) -> FileEntry:
        """Create a directory (with parents). Idempotent.

        Args:
            path (str): Absolute path of the directory to create.

        Returns:
            FileEntry: The created (or already-existing) directory entry.
        """
        resp = await self._http.post(
            f"/v1/capsules/{self._capsule_id}/files/mkdir",
            json={"path": path},
        )
        if resp.status_code == 409:
            try:
                body = resp.json()
                if body.get("error", {}).get("code") == "conflict":
                    parent = os.path.dirname(path)
                    name = os.path.basename(path)
                    for entry in await self.list(parent, depth=1):
                        if entry.name == name:
                            return entry
            except Exception:
                pass
        parsed = MakeDirResponse.model_validate(handle_response(resp))
        if parsed.entry is None:
            raise RuntimeError("mkdir response missing entry")
        return parsed.entry

    async def remove(self, path: str) -> None:
        """Remove a file or directory recursively.

        Args:
            path (str): Absolute path to remove.

        Raises:
            WrennNotFoundError: If the path does not exist.
        """
        resp = await self._http.post(
            f"/v1/capsules/{self._capsule_id}/files/remove",
            json={"path": path},
        )
        handle_response(resp)

    async def upload_stream(self, path: str, stream: AsyncIterator[bytes]) -> None:
        """Stream a large file into the capsule.

        Prefer this over :meth:`write` when the file is too large to hold in
        memory.

        Args:
            path (str): Absolute destination path inside the capsule.
            stream (AsyncIterator[bytes]): Async iterable of byte chunks to
                upload.
        """
        boundary = os.urandom(16).hex().encode("utf-8")

        async def _multipart() -> AsyncIterator[bytes]:
            yield b"--" + boundary + b"\r\n"
            yield b'Content-Disposition: form-data; name="path"\r\n\r\n'
            yield path.encode("utf-8") + b"\r\n"
            yield b"--" + boundary + b"\r\n"
            yield b'Content-Disposition: form-data; name="file"; filename="upload.bin"\r\n'
            yield b"Content-Type: application/octet-stream\r\n\r\n"
            async for chunk in stream:
                yield chunk if isinstance(chunk, bytes) else chunk.encode("utf-8")
            yield b"\r\n--" + boundary + b"--\r\n"

        resp = await self._http.post(
            f"/v1/capsules/{self._capsule_id}/files/stream/write",
            content=_multipart(),
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary.decode('utf-8')}"
            },
        )
        _raise_for_status(resp)

    async def download_stream(self, path: str) -> AsyncIterator[bytes]:
        """Stream a large file out of the capsule.

        Prefer this over :meth:`read_bytes` when the file is too large to hold
        in memory.

        Args:
            path (str): Absolute path to the file inside the capsule.

        Yields:
            bytes: Successive byte chunks of the file.

        Raises:
            WrennNotFoundError: If the path does not exist.
        """
        async with self._http.stream(
            "POST",
            f"/v1/capsules/{self._capsule_id}/files/stream/read",
            json={"path": path},
        ) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_bytes():
                yield chunk
