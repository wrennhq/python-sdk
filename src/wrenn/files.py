from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import httpx

from wrenn.exceptions import WrennNotFoundError, handle_response
from wrenn.models import FileEntry, ListDirResponse, MakeDirResponse


class Files:
    """Sync filesystem interface. Accessed via ``capsule.files``."""

    def __init__(self, capsule_id: str, http: httpx.Client) -> None:
        self._capsule_id = capsule_id
        self._http = http

    def read(self, path: str) -> str:
        """Read a file as a UTF-8 string."""
        return self.read_bytes(path).decode("utf-8", errors="replace")

    def read_bytes(self, path: str) -> bytes:
        """Read a file as raw bytes."""
        resp = self._http.post(
            f"/v1/capsules/{self._capsule_id}/files/read",
            json={"path": path},
        )
        resp.raise_for_status()
        return resp.content

    def write(self, path: str, data: str | bytes) -> None:
        """Write data to a file inside the capsule."""
        if isinstance(data, str):
            data = data.encode("utf-8")
        resp = self._http.post(
            f"/v1/capsules/{self._capsule_id}/files/write",
            files={"file": ("upload", data)},
            data={"path": path},
        )
        resp.raise_for_status()

    def list(self, path: str, depth: int = 1) -> list[FileEntry]:
        """List directory contents."""
        resp = self._http.post(
            f"/v1/capsules/{self._capsule_id}/files/list",
            json={"path": path, "depth": depth},
        )
        parsed = ListDirResponse.model_validate(handle_response(resp))
        return parsed.entries or []

    def exists(self, path: str) -> bool:
        """Check whether a path exists inside the capsule."""
        parent = os.path.dirname(path)
        name = os.path.basename(path)
        try:
            entries = self.list(parent, depth=1)
        except WrennNotFoundError:
            return False
        return any(e.name == name for e in entries)

    def make_dir(self, path: str) -> FileEntry:
        """Create a directory (with parents). Idempotent."""
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
        """Remove a file or directory recursively."""
        resp = self._http.post(
            f"/v1/capsules/{self._capsule_id}/files/remove",
            json={"path": path},
        )
        handle_response(resp)

    def upload_stream(self, path: str, stream: Iterator[bytes]) -> None:
        """Streaming upload for large files."""
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
        resp.raise_for_status()

    def download_stream(self, path: str) -> Iterator[bytes]:
        """Streaming download for large files."""
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
        """Read a file as a UTF-8 string."""
        data = await self.read_bytes(path)
        return data.decode("utf-8", errors="replace")

    async def read_bytes(self, path: str) -> bytes:
        """Read a file as raw bytes."""
        resp = await self._http.post(
            f"/v1/capsules/{self._capsule_id}/files/read",
            json={"path": path},
        )
        resp.raise_for_status()
        return resp.content

    async def write(self, path: str, data: str | bytes) -> None:
        """Write data to a file inside the capsule."""
        if isinstance(data, str):
            data = data.encode("utf-8")
        resp = await self._http.post(
            f"/v1/capsules/{self._capsule_id}/files/write",
            files={"file": ("upload", data)},
            data={"path": path},
        )
        resp.raise_for_status()

    async def list(self, path: str, depth: int = 1) -> list[FileEntry]:
        """List directory contents."""
        resp = await self._http.post(
            f"/v1/capsules/{self._capsule_id}/files/list",
            json={"path": path, "depth": depth},
        )
        parsed = ListDirResponse.model_validate(handle_response(resp))
        return parsed.entries or []

    async def exists(self, path: str) -> bool:
        """Check whether a path exists inside the capsule."""
        parent = os.path.dirname(path)
        name = os.path.basename(path)
        try:
            entries = await self.list(parent, depth=1)
        except WrennNotFoundError:
            return False
        return any(e.name == name for e in entries)

    async def make_dir(self, path: str) -> FileEntry:
        """Create a directory (with parents). Idempotent."""
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
        """Remove a file or directory recursively."""
        resp = await self._http.post(
            f"/v1/capsules/{self._capsule_id}/files/remove",
            json={"path": path},
        )
        handle_response(resp)

    async def upload_stream(self, path: str, stream: AsyncIterator[bytes]) -> None:
        """Streaming upload for large files."""
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
        resp.raise_for_status()

    async def download_stream(self, path: str) -> AsyncIterator[bytes]:
        """Streaming download for large files."""
        async with self._http.stream(
            "POST",
            f"/v1/capsules/{self._capsule_id}/files/stream/read",
            json={"path": path},
        ) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_bytes():
                yield chunk
