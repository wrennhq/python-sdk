from __future__ import annotations

from wrenn.client import WrennClient

from .conftest import requires_auth


@requires_auth
class TestStreamUploadDownload:
    def test_stream_upload_and_download(self, client: WrennClient):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            chunks = [b"chunk0_", b"chunk1_", b"chunk2"]

            def data_gen():
                yield from chunks

            cap.stream_upload("/tmp/stream_test.bin", data_gen())
            downloaded = cap.download("/tmp/stream_test.bin")
            assert downloaded == b"chunk0_chunk1_chunk2"

    def test_stream_download_large(self, client: WrennClient):
        with client.capsules.create(template="minimal", timeout_sec=120) as cap:
            cap.wait_ready(timeout=60, interval=1)
            content = b"x" * 65536 * 3
            cap.upload("/tmp/large.bin", content)
            collected = b""
            for chunk in cap.stream_download("/tmp/large.bin"):
                collected += chunk
            assert collected == content
