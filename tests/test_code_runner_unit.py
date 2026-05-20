from __future__ import annotations

import importlib
import json
import sys
import warnings
from unittest.mock import patch

import httpx
import pytest
import respx

from wrenn.code_runner import (
    AsyncCapsule,
    Capsule,
    Execution,
    Logs,
    Result,
)
from wrenn.code_runner.capsule import DEFAULT_KERNEL, DEFAULT_TEMPLATE

BASE = "https://app.wrenn.dev/api"
API_KEY = "wrn_test1234567890abcdef12345678"


# ───────────────────────── Result / Execution models ─────────────────────────


class TestResultFromBundle:
    def test_unpacks_known_mime_types(self):
        r = Result.from_bundle(
            {
                "text/plain": "42",
                "text/html": "<b>42</b>",
                "image/png": "iVBORw0KGgo=",
                "application/json": {"x": 1},
            },
            is_main_result=True,
        )
        assert r.text == "42"
        assert r.html == "<b>42</b>"
        assert r.png == "iVBORw0KGgo="
        assert r.json == {"x": 1}
        assert r.is_main_result is True
        assert r.extra is None

    def test_unknown_mime_lands_in_extra(self):
        r = Result.from_bundle({"application/vnd.custom+json": "{}"})
        assert r.extra == {"application/vnd.custom+json": "{}"}
        assert r.is_main_result is False

    @pytest.mark.parametrize(
        "raw",
        [
            "'hello'",
            '"hello"',
            "hello",
            "'x",
            "''",
            "'",
            "'it\\'s'",
            "{'a': 1}",
            "[1, 2, 3]",
        ],
    )
    def test_text_plain_preserved_verbatim(self, raw):
        """``text/plain`` is the Jupyter repr — pass through unchanged.
        Stripping outer quotes would lose string identity (a string
        ``'2'`` would become indistinguishable from the int ``2``)."""
        r = Result.from_bundle({"text/plain": raw})
        assert r.text == raw

    def test_formats_lists_present_fields(self):
        r = Result.from_bundle({"text/plain": "x", "image/svg+xml": "<svg/>"})
        fmts = r.formats()
        assert "text" in fmts
        assert "svg" in fmts
        assert "html" not in fmts

    def test_formats_includes_extra(self):
        r = Result.from_bundle({"application/x-foo": "bar"})
        assert "application/x-foo" in r.formats()

    def test_all_mime_types_map(self):
        r = Result.from_bundle(
            {
                "text/plain": "a",
                "text/html": "b",
                "text/markdown": "c",
                "image/svg+xml": "d",
                "image/png": "e",
                "image/jpeg": "f",
                "application/pdf": "g",
                "text/latex": "h",
                "application/json": {"k": 1},
                "application/javascript": "j",
            }
        )
        for attr in (
            "text",
            "html",
            "markdown",
            "svg",
            "png",
            "jpeg",
            "pdf",
            "latex",
            "json",
            "javascript",
        ):
            assert getattr(r, attr) is not None


class TestExecution:
    def test_text_returns_main_result(self):
        ex = Execution(
            results=[
                Result(text="display", is_main_result=False),
                Result(text="main", is_main_result=True),
            ]
        )
        assert ex.text == "main"

    def test_text_none_when_no_main(self):
        ex = Execution(results=[Result(text="x", is_main_result=False)])
        assert ex.text is None

    def test_defaults(self):
        ex = Execution()
        assert ex.results == []
        assert isinstance(ex.logs, Logs)
        assert ex.error is None
        assert ex.execution_count is None


# ───────────────────────── deprecation alias ─────────────────────────


class TestDeprecationAlias:
    def test_code_interpreter_emits_warning_on_import(self):
        # Force a fresh import to observe the warning.
        sys.modules.pop("wrenn.code_interpreter", None)
        # Reset the one-shot flag in case the module was previously imported.
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            ci = importlib.import_module("wrenn.code_interpreter")
            ci.warnings_emitted = False  # type: ignore[attr-defined]
            # Re-import to trigger again
            sys.modules.pop("wrenn.code_interpreter", None)
            importlib.import_module("wrenn.code_interpreter")
            msgs = [
                str(w.message)
                for w in captured
                if issubclass(w.category, FutureWarning)
            ]
        assert any("code_interpreter" in m and "code_runner" in m for m in msgs)

    def test_alias_re_exports_same_classes(self):
        from wrenn import code_interpreter as ci

        assert ci.Capsule is Capsule
        assert ci.AsyncCapsule is AsyncCapsule
        assert ci.Execution is Execution
        assert ci.Result is Result

    def test_sandbox_attr_deprecated(self):
        from wrenn import code_runner as cr

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            S = cr.Sandbox
        assert S is cr.Capsule
        assert any(
            issubclass(w.category, FutureWarning) and "Sandbox" in str(w.message)
            for w in captured
        )


# ───────────────────────── Capsule (mock HTTP) ─────────────────────────


@respx.mock
def _make_capsule(capsule_id: str = "sb-1") -> Capsule:
    respx.post(f"{BASE}/v1/capsules").respond(
        202,
        json={"id": capsule_id, "status": "starting", "template": DEFAULT_TEMPLATE},
    )
    return Capsule(api_key=API_KEY, base_url=BASE)


class TestCapsuleDefaults:
    @respx.mock
    def test_default_template_sent(self):
        route = respx.post(f"{BASE}/v1/capsules").respond(
            202, json={"id": "sb-1", "status": "starting"}
        )
        Capsule(api_key=API_KEY, base_url=BASE)
        body = json.loads(route.calls[0].request.content)
        assert body["template"] == DEFAULT_TEMPLATE
        assert DEFAULT_TEMPLATE == "code-runner-beta"

    @respx.mock
    def test_explicit_template_override(self):
        route = respx.post(f"{BASE}/v1/capsules").respond(
            202, json={"id": "sb-1", "status": "starting"}
        )
        Capsule(template="other-template", api_key=API_KEY, base_url=BASE)
        body = json.loads(route.calls[0].request.content)
        assert body["template"] == "other-template"

    @respx.mock
    def test_create_classmethod(self):
        respx.post(f"{BASE}/v1/capsules").respond(
            202, json={"id": "sb-2", "status": "starting"}
        )
        c = Capsule.create(api_key=API_KEY, base_url=BASE)
        assert c.capsule_id == "sb-2"

    @respx.mock
    def test_default_kernel_name(self):
        respx.post(f"{BASE}/v1/capsules").respond(
            202, json={"id": "sb-1", "status": "starting"}
        )
        c = Capsule(api_key=API_KEY, base_url=BASE)
        assert c._kernel_name == DEFAULT_KERNEL == "wrenn"

    @respx.mock
    def test_custom_kernel_name(self):
        respx.post(f"{BASE}/v1/capsules").respond(
            202, json={"id": "sb-1", "status": "starting"}
        )
        c = Capsule(kernel="python3", api_key=API_KEY, base_url=BASE)
        assert c._kernel_name == "python3"


class TestCtorFailureSafe:
    """Bug regression: __del__ must not crash when ctor fails before
    _proxy_client is initialised."""

    @respx.mock
    def test_del_safe_when_ctor_fails(self):
        respx.post(f"{BASE}/v1/capsules").respond(
            404,
            json={"error": {"code": "not_found", "message": "no template"}},
        )
        from wrenn.exceptions import WrennNotFoundError

        with pytest.raises(WrennNotFoundError):
            Capsule(api_key=API_KEY, base_url=BASE)
        # If we got here without an AttributeError on __del__, we're good.

    @respx.mock
    def test_close_idempotent(self):
        c = _make_capsule()
        c.close()
        c.close()  # second call must not raise


# ───────────────────────── _ensure_kernel ─────────────────────────


class TestEnsureKernel:
    @respx.mock
    def test_creates_kernel_with_wrenn_name_when_none_exist(self):
        c = _make_capsule()
        proxy_base = "https://8888-sb-1.wrenn.dev"
        list_route = respx.get(f"{proxy_base}/api/kernels").respond(200, json=[])
        create_route = respx.post(f"{proxy_base}/api/kernels").respond(
            201, json={"id": "k-new", "name": "wrenn"}
        )

        kid = c._ensure_kernel()
        assert kid == "k-new"
        # Body must request the wrenn kernelspec.
        body = json.loads(create_route.calls[0].request.content)
        assert body == {"name": "wrenn"}
        assert list_route.called

    @respx.mock
    def test_reuses_existing_wrenn_kernel(self):
        c = _make_capsule()
        proxy_base = "https://8888-sb-1.wrenn.dev"
        respx.get(f"{proxy_base}/api/kernels").respond(
            200,
            json=[
                {"id": "k-other", "name": "python3"},
                {"id": "k-wrenn", "name": "wrenn"},
            ],
        )
        create = respx.post(f"{proxy_base}/api/kernels").respond(201, json={})
        kid = c._ensure_kernel()
        assert kid == "k-wrenn"
        assert not create.called

    @respx.mock
    def test_creates_when_only_other_kernels_exist(self):
        c = _make_capsule()
        proxy_base = "https://8888-sb-1.wrenn.dev"
        respx.get(f"{proxy_base}/api/kernels").respond(
            200, json=[{"id": "k-other", "name": "python3"}]
        )
        respx.post(f"{proxy_base}/api/kernels").respond(
            201, json={"id": "k-new", "name": "wrenn"}
        )
        kid = c._ensure_kernel()
        assert kid == "k-new"

    @respx.mock
    def test_caches_kernel_id(self):
        c = _make_capsule()
        proxy_base = "https://8888-sb-1.wrenn.dev"
        route = respx.get(f"{proxy_base}/api/kernels").respond(
            200, json=[{"id": "k-1", "name": "wrenn"}]
        )
        c._ensure_kernel()
        c._ensure_kernel()
        assert route.call_count == 1

    @respx.mock
    def test_custom_kernel_name_sent(self):
        respx.post(f"{BASE}/v1/capsules").respond(
            202, json={"id": "sb-1", "status": "starting"}
        )
        c = Capsule(kernel="python3", api_key=API_KEY, base_url=BASE)
        proxy_base = "https://8888-sb-1.wrenn.dev"
        respx.get(f"{proxy_base}/api/kernels").respond(200, json=[])
        create = respx.post(f"{proxy_base}/api/kernels").respond(
            201, json={"id": "k-py", "name": "python3"}
        )
        c._ensure_kernel()
        body = json.loads(create.calls[0].request.content)
        assert body == {"name": "python3"}

    @respx.mock
    def test_retries_on_5xx_then_succeeds(self):
        c = _make_capsule()
        proxy_base = "https://8888-sb-1.wrenn.dev"
        responses = [
            httpx.Response(503),
            httpx.Response(200, json=[{"id": "k-1", "name": "wrenn"}]),
        ]
        respx.get(f"{proxy_base}/api/kernels").mock(side_effect=responses)
        with patch("time.sleep"):
            kid = c._ensure_kernel(jupyter_timeout=5)
        assert kid == "k-1"

    @respx.mock
    def test_raises_on_4xx(self):
        c = _make_capsule()
        proxy_base = "https://8888-sb-1.wrenn.dev"
        respx.get(f"{proxy_base}/api/kernels").respond(401)
        with pytest.raises(httpx.HTTPStatusError):
            c._ensure_kernel(jupyter_timeout=2)

    @respx.mock
    def test_timeout_raises(self):
        c = _make_capsule()
        proxy_base = "https://8888-sb-1.wrenn.dev"
        respx.get(f"{proxy_base}/api/kernels").respond(503)
        with patch("time.sleep"):
            with pytest.raises(TimeoutError):
                c._ensure_kernel(jupyter_timeout=0.01)


# ───────────────────────── build_execute_request ─────────────────────────


class TestJupyterRequest:
    def test_structure(self):
        from wrenn.code_runner._protocol import build_execute_request

        msg = build_execute_request("print(1)")
        assert msg["channel"] == "shell"
        assert msg["header"]["msg_type"] == "execute_request"
        assert msg["content"]["code"] == "print(1)"
        assert msg["content"]["silent"] is False
        assert msg["content"]["store_history"] is True
        assert msg["content"]["allow_stdin"] is False
        assert msg["content"]["stop_on_error"] is True
        # msg_id must be a uuid-shaped string
        assert len(msg["header"]["msg_id"]) == 36

    def test_unique_msg_id_per_call(self):
        from wrenn.code_runner._protocol import build_execute_request

        a = build_execute_request("x")
        b = build_execute_request("x")
        assert a["header"]["msg_id"] != b["header"]["msg_id"]


# ───────────────────────── run_code (WS-mocked) ─────────────────────────


def _wrap(msg_type: str, parent_id: str, content: dict) -> dict:
    return {
        "msg_type": msg_type,
        "header": {"msg_type": msg_type},
        "parent_header": {"msg_id": parent_id},
        "content": content,
    }


class _FakeWS:
    """Minimal sync httpx_ws-shaped fake.

    If ``frames_factory`` yields an ``Exception`` instance, the fake
    raises it instead of returning the value — useful for testing
    disconnect / network-error paths.
    """

    def __init__(self, frames_factory):
        self._frames_factory = frames_factory
        self._sent: list[str] = []
        self._iter = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def send_text(self, s: str) -> None:
        self._sent.append(s)
        parent_id = json.loads(s)["header"]["msg_id"]
        self._iter = iter(self._frames_factory(parent_id))

    def receive_json(self, timeout: float = 0):
        assert self._iter is not None
        try:
            nxt = next(self._iter)
        except StopIteration:
            raise TimeoutError("no more frames")
        if isinstance(nxt, BaseException):
            raise nxt
        return nxt


class _FakeAsyncWS:
    def __init__(self, frames_factory):
        self._frames_factory = frames_factory
        self._iter = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def send_text(self, s: str) -> None:
        parent_id = json.loads(s)["header"]["msg_id"]
        self._iter = iter(self._frames_factory(parent_id))

    async def receive_json(self):
        assert self._iter is not None
        try:
            nxt = next(self._iter)
        except StopIteration:
            raise TimeoutError("no more frames")
        if isinstance(nxt, BaseException):
            raise nxt
        return nxt


class TestRunCode:
    @respx.mock
    def _make_ready(self):
        c = _make_capsule()
        # Pre-populate kernel so run_code skips ensure.
        c._kernel_id = "k-1"
        return c

    def test_stream_stdout_and_stderr(self):
        c = self._make_ready()

        def frames(pid):
            yield _wrap("stream", pid, {"name": "stdout", "text": "hello\n"})
            yield _wrap("stream", pid, {"name": "stderr", "text": "warn\n"})
            yield _wrap("status", pid, {"execution_state": "idle"})

        stdout_chunks, stderr_chunks = [], []
        with patch(
            "wrenn.code_runner.capsule.httpx_ws.connect_ws",
            return_value=_FakeWS(frames),
        ):
            ex = c.run_code(
                "print('hello')",
                on_stdout=stdout_chunks.append,
                on_stderr=stderr_chunks.append,
            )
        assert ex.logs.stdout == ["hello\n"]
        assert ex.logs.stderr == ["warn\n"]
        assert stdout_chunks == ["hello\n"]
        assert stderr_chunks == ["warn\n"]
        assert ex.error is None

    def test_execute_result_main_and_display_data(self):
        c = self._make_ready()

        def frames(pid):
            yield _wrap(
                "display_data",
                pid,
                {"data": {"image/png": "BASE64"}},
            )
            yield _wrap(
                "execute_result",
                pid,
                {
                    "execution_count": 7,
                    "data": {"text/plain": "'42'"},
                },
            )
            yield _wrap("status", pid, {"execution_state": "idle"})

        results = []
        with patch(
            "wrenn.code_runner.capsule.httpx_ws.connect_ws",
            return_value=_FakeWS(frames),
        ):
            ex = c.run_code("'42'", on_result=results.append)
        assert ex.execution_count == 7
        assert len(ex.results) == 2
        main = [r for r in ex.results if r.is_main_result]
        assert len(main) == 1
        assert main[0].text == "'42'"  # text/plain preserved verbatim
        display = [r for r in ex.results if not r.is_main_result]
        assert display[0].png == "BASE64"
        assert ex.text == "'42'"
        assert len(results) == 2

    def test_error_message(self):
        c = self._make_ready()

        def frames(pid):
            yield _wrap(
                "error",
                pid,
                {
                    "ename": "NameError",
                    "evalue": "name 'x' is not defined",
                    "traceback": ["line1", "line2"],
                },
            )
            yield _wrap("status", pid, {"execution_state": "idle"})

        errors = []
        with patch(
            "wrenn.code_runner.capsule.httpx_ws.connect_ws",
            return_value=_FakeWS(frames),
        ):
            ex = c.run_code("x", on_error=errors.append)
        assert ex.error is not None
        assert ex.error.name == "NameError"
        assert ex.error.value == "name 'x' is not defined"
        assert ex.error.traceback == "line1\nline2"
        assert len(errors) == 1

    def test_ignores_frames_with_other_parent(self):
        c = self._make_ready()

        def frames(pid):
            yield _wrap("stream", "other-id", {"name": "stdout", "text": "drop\n"})
            yield _wrap("stream", pid, {"name": "stdout", "text": "keep\n"})
            yield _wrap("status", pid, {"execution_state": "idle"})

        with patch(
            "wrenn.code_runner.capsule.httpx_ws.connect_ws",
            return_value=_FakeWS(frames),
        ):
            ex = c.run_code("print('keep')")
        assert ex.logs.stdout == ["keep\n"]

    def test_unsupported_language_raises(self):
        c = self._make_ready()
        with pytest.raises(ValueError, match="not supported"):
            c.run_code("console.log('x')", language="javascript")

    def test_idle_status_terminates_loop(self):
        c = self._make_ready()
        called = {"n": 0}

        def frames(pid):
            yield _wrap("status", pid, {"execution_state": "idle"})
            # Following frame must never be consumed.
            called["n"] += 1
            yield _wrap("stream", pid, {"name": "stdout", "text": "post-idle\n"})

        with patch(
            "wrenn.code_runner.capsule.httpx_ws.connect_ws",
            return_value=_FakeWS(frames),
        ):
            ex = c.run_code("pass")
        assert ex.logs.stdout == []


class TestAsyncRunCode:
    @respx.mock
    def _make_ready(self):
        respx.post(f"{BASE}/v1/capsules").respond(
            202, json={"id": "sb-1", "status": "starting"}
        )
        from wrenn.client import AsyncWrennClient
        from wrenn.models import Capsule as CapsuleModel

        client = AsyncWrennClient(api_key=API_KEY, base_url=BASE)
        info = CapsuleModel(id="sb-1")
        c = AsyncCapsule(_capsule_id="sb-1", _client=client, _info=info)
        c._kernel_id = "k-1"
        return c

    @pytest.mark.asyncio
    async def test_stream_and_result(self):
        c = self._make_ready()

        def frames(pid):
            yield _wrap("stream", pid, {"name": "stdout", "text": "hi\n"})
            yield _wrap(
                "execute_result",
                pid,
                {"execution_count": 1, "data": {"text/plain": "7"}},
            )
            yield _wrap("status", pid, {"execution_state": "idle"})

        with patch(
            "wrenn.code_runner.async_capsule.httpx_ws.aconnect_ws",
            return_value=_FakeAsyncWS(frames),
        ):
            ex = await c.run_code("7")
        assert ex.logs.stdout == ["hi\n"]
        assert ex.text == "7"
        assert ex.execution_count == 1
        await c.close()

    @pytest.mark.asyncio
    async def test_async_default_kernel(self):
        c = self._make_ready()
        assert c._kernel_name == "wrenn"
        await c.close()


class TestAsyncCtorFailureSafe:
    def test_del_safe_when_not_constructed(self):
        # Build without ever calling __init__'s parent path that needs network,
        # by hand-poking attributes the way create() failure would leave them.
        c = AsyncCapsule.__new__(AsyncCapsule)
        # __del__ should be safe even with no attrs.
        c.__del__()


# ───────────────────────── run_code error-path regressions (B2) ─────────────


class TestRunCodeErrorPaths:
    """Sync run_code timeout / disconnect / unexpected-exception behavior."""

    def _ready(self):
        return TestRunCode()._make_ready()

    def test_timeout_when_no_idle_received(self):
        c = self._ready()

        def frames(pid):
            yield _wrap("stream", pid, {"name": "stdout", "text": "partial\n"})
            # No idle frame; loop exits via StopIteration → TimeoutError.

        errors = []
        with patch(
            "wrenn.code_runner.capsule.httpx_ws.connect_ws",
            return_value=_FakeWS(frames),
        ):
            ex = c.run_code("x", on_error=errors.append)
        assert ex.timed_out is True
        assert ex.error is not None
        assert ex.error.name == "Timeout"
        assert "exceeded" in ex.error.value
        assert ex.logs.stdout == ["partial\n"]
        assert len(errors) == 1

    def test_disconnect_sets_disconnected_error(self):
        c = self._ready()
        import httpx_ws

        def frames(pid):
            yield _wrap("stream", pid, {"name": "stdout", "text": "hi\n"})
            yield httpx_ws.WebSocketDisconnect(code=1000, reason="bye")

        errors = []
        with patch(
            "wrenn.code_runner.capsule.httpx_ws.connect_ws",
            return_value=_FakeWS(frames),
        ):
            ex = c.run_code("x", on_error=errors.append)
        assert ex.timed_out is True
        assert ex.error is not None
        assert ex.error.name == "Disconnected"
        assert ex.logs.stdout == ["hi\n"]
        assert len(errors) == 1

    def test_unexpected_exception_propagates(self):
        c = self._ready()

        def frames(pid):
            yield RuntimeError("WS broken in unexpected way")

        with patch(
            "wrenn.code_runner.capsule.httpx_ws.connect_ws",
            return_value=_FakeWS(frames),
        ):
            with pytest.raises(RuntimeError, match="WS broken"):
                c.run_code("x")

    def test_clean_exit_does_not_set_timed_out(self):
        c = self._ready()

        def frames(pid):
            yield _wrap("status", pid, {"execution_state": "idle"})

        with patch(
            "wrenn.code_runner.capsule.httpx_ws.connect_ws",
            return_value=_FakeWS(frames),
        ):
            ex = c.run_code("pass")
        assert ex.timed_out is False
        assert ex.error is None


# ───────────────────────── Async run_code parity ──────────────────────────


class TestAsyncRunCodeErrorPaths:
    def _ready(self):
        return TestAsyncRunCode()._make_ready()

    @pytest.mark.asyncio
    async def test_async_timeout_when_no_idle(self):
        c = self._ready()

        def frames(pid):
            yield _wrap("stream", pid, {"name": "stdout", "text": "partial\n"})

        errors = []
        with patch(
            "wrenn.code_runner.async_capsule.httpx_ws.aconnect_ws",
            return_value=_FakeAsyncWS(frames),
        ):
            ex = await c.run_code("x", on_error=errors.append)
        assert ex.timed_out is True
        assert ex.error is not None
        assert ex.error.name == "Timeout"
        assert ex.logs.stdout == ["partial\n"]
        assert len(errors) == 1
        await c.close()

    @pytest.mark.asyncio
    async def test_async_disconnect_sets_disconnected_error(self):
        c = self._ready()
        import httpx_ws

        def frames(pid):
            yield httpx_ws.WebSocketNetworkError("network blip")

        errors = []
        with patch(
            "wrenn.code_runner.async_capsule.httpx_ws.aconnect_ws",
            return_value=_FakeAsyncWS(frames),
        ):
            ex = await c.run_code("x", on_error=errors.append)
        assert ex.timed_out is True
        assert ex.error is not None
        assert ex.error.name == "Disconnected"
        assert len(errors) == 1
        await c.close()

    @pytest.mark.asyncio
    async def test_async_unexpected_exception_propagates(self):
        c = self._ready()

        def frames(pid):
            yield RuntimeError("unexpected WS death")

        with patch(
            "wrenn.code_runner.async_capsule.httpx_ws.aconnect_ws",
            return_value=_FakeAsyncWS(frames),
        ):
            with pytest.raises(RuntimeError, match="unexpected WS"):
                await c.run_code("x")
        await c.close()

    @pytest.mark.asyncio
    async def test_async_unsupported_language_raises(self):
        c = self._ready()
        with pytest.raises(ValueError, match="not supported"):
            await c.run_code("console.log('x')", language="javascript")
        await c.close()


# ───────────────────────── Async _ensure_kernel parity ───────────────────────


@respx.mock
def _make_async_capsule(capsule_id: str = "sb-1") -> AsyncCapsule:
    """Construct an AsyncCapsule without going through ``create()``."""
    from wrenn.client import AsyncWrennClient
    from wrenn.models import Capsule as CapsuleModel

    client = AsyncWrennClient(api_key=API_KEY, base_url=BASE)
    info = CapsuleModel(id=capsule_id)
    return AsyncCapsule(_capsule_id=capsule_id, _client=client, _info=info)


class TestAsyncEnsureKernel:
    @pytest.mark.asyncio
    @respx.mock
    async def test_async_creates_kernel_when_none_exist(self):
        c = _make_async_capsule()
        proxy_base = "https://8888-sb-1.wrenn.dev"
        list_route = respx.get(f"{proxy_base}/api/kernels").respond(200, json=[])
        create_route = respx.post(f"{proxy_base}/api/kernels").respond(
            201, json={"id": "k-new", "name": "wrenn"}
        )
        kid = await c._ensure_kernel()
        assert kid == "k-new"
        body = json.loads(create_route.calls[0].request.content)
        assert body == {"name": "wrenn"}
        assert list_route.called
        await c.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_reuses_existing_wrenn_kernel(self):
        c = _make_async_capsule()
        proxy_base = "https://8888-sb-1.wrenn.dev"
        respx.get(f"{proxy_base}/api/kernels").respond(
            200,
            json=[
                {"id": "k-other", "name": "python3"},
                {"id": "k-wrenn", "name": "wrenn"},
            ],
        )
        create = respx.post(f"{proxy_base}/api/kernels").respond(201, json={})
        kid = await c._ensure_kernel()
        assert kid == "k-wrenn"
        assert not create.called
        await c.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_retries_on_5xx_then_succeeds(self):
        c = _make_async_capsule()
        proxy_base = "https://8888-sb-1.wrenn.dev"
        responses = [
            httpx.Response(503),
            httpx.Response(200, json=[{"id": "k-1", "name": "wrenn"}]),
        ]
        respx.get(f"{proxy_base}/api/kernels").mock(side_effect=responses)
        with patch("asyncio.sleep") as sleep_mock:

            async def _noop(_s):
                return None

            sleep_mock.side_effect = _noop
            kid = await c._ensure_kernel(jupyter_timeout=5)
        assert kid == "k-1"
        await c.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_raises_on_4xx(self):
        c = _make_async_capsule()
        proxy_base = "https://8888-sb-1.wrenn.dev"
        respx.get(f"{proxy_base}/api/kernels").respond(401)
        with pytest.raises(httpx.HTTPStatusError):
            await c._ensure_kernel(jupyter_timeout=2)
        await c.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_caches_kernel_id(self):
        c = _make_async_capsule()
        proxy_base = "https://8888-sb-1.wrenn.dev"
        route = respx.get(f"{proxy_base}/api/kernels").respond(
            200, json=[{"id": "k-1", "name": "wrenn"}]
        )
        await c._ensure_kernel()
        await c._ensure_kernel()
        assert route.call_count == 1
        await c.close()
