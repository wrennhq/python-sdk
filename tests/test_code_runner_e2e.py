from __future__ import annotations

import asyncio
import os
import warnings
from pathlib import Path

import pytest

from wrenn.code_runner import (
    AsyncCapsule,
    Capsule,
    Execution,
    Result,
)

pytestmark = pytest.mark.integration

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


# ───────────────────────── Sync e2e ─────────────────────────


class TestCodeRunnerSync:
    """Shared capsule — kernel state persists across tests."""

    capsule: Capsule

    @classmethod
    def setup_class(cls):
        _ensure_env()
        cls.capsule = Capsule(wait=True)

    @classmethod
    def teardown_class(cls):
        try:
            cls.capsule.destroy()
        except Exception:
            pass

    def test_uses_code_runner_beta_template(self):
        assert self.capsule.info is not None
        assert self.capsule.info.template == "code-runner-beta"

    def test_default_kernel_name_is_wrenn(self):
        assert self.capsule._kernel_name == "wrenn"

    def test_simple_expression(self):
        ex = self.capsule.run_code("1 + 1")
        assert isinstance(ex, Execution)
        assert ex.error is None
        assert ex.text == "2"
        assert ex.execution_count is not None
        assert ex.execution_count >= 1

    def test_print_captures_stdout(self):
        ex = self.capsule.run_code("print('hello world')")
        assert ex.error is None
        joined = "".join(ex.logs.stdout)
        assert "hello world" in joined

    def test_stderr_captured(self):
        ex = self.capsule.run_code("import sys; sys.stderr.write('an error\\n')")
        assert ex.error is None
        joined = "".join(ex.logs.stderr)
        assert "an error" in joined

    def test_kernel_state_persists_across_calls(self):
        self.capsule.run_code("persistent_value = 12345")
        ex = self.capsule.run_code("persistent_value")
        assert ex.text == "12345"

    def test_import_persists(self):
        self.capsule.run_code("import math")
        ex = self.capsule.run_code("round(math.pi, 4)")
        assert ex.text == "3.1416"

    def test_function_definition_persists(self):
        self.capsule.run_code(
            "def fib(n):\n"
            "    a, b = 0, 1\n"
            "    for _ in range(n):\n"
            "        a, b = b, a + b\n"
            "    return a\n"
        )
        ex = self.capsule.run_code("fib(10)")
        assert ex.text == "55"

    def test_class_definition_persists(self):
        self.capsule.run_code(
            "class Counter:\n"
            "    def __init__(self): self.n = 0\n"
            "    def inc(self): self.n += 1; return self.n\n"
            "c = Counter()\n"
        )
        ex = self.capsule.run_code("c.inc(); c.inc(); c.inc(); c.n")
        assert ex.text == "3"

    def test_exception_captured(self):
        ex = self.capsule.run_code("raise ValueError('boom')")
        assert ex.error is not None
        assert ex.error.name == "ValueError"
        assert "boom" in ex.error.value
        assert "ValueError" in ex.error.traceback

    def test_name_error(self):
        ex = self.capsule.run_code("undefined_symbol_xyz")
        assert ex.error is not None
        assert ex.error.name == "NameError"

    def test_syntax_error(self):
        ex = self.capsule.run_code("def )(\n")
        assert ex.error is not None
        assert "SyntaxError" in ex.error.name

    def test_callbacks_fire(self):
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        results: list[Result] = []
        errors = []
        self.capsule.run_code(
            "import sys\nprint('on stdout')\nsys.stderr.write('on stderr\\n')\n42\n",
            on_stdout=stdout_chunks.append,
            on_stderr=stderr_chunks.append,
            on_result=results.append,
            on_error=errors.append,
        )
        assert any("on stdout" in c for c in stdout_chunks)
        assert any("on stderr" in c for c in stderr_chunks)
        assert any(r.text == "42" for r in results)
        assert errors == []

    def test_multi_line_output(self):
        ex = self.capsule.run_code("for i in range(3):\n    print(i)\n")
        joined = "".join(ex.logs.stdout)
        assert "0" in joined and "1" in joined and "2" in joined

    def test_no_main_result_when_statement_only(self):
        ex = self.capsule.run_code("x = 5")
        assert ex.text is None
        assert ex.error is None

    def test_html_repr_result(self):
        ex = self.capsule.run_code(
            "from IPython.display import HTML\nHTML('<b>bold</b>')"
        )
        assert ex.error is None
        main = [r for r in ex.results if r.is_main_result]
        assert main, "expected execute_result"
        assert main[0].html is not None
        assert "<b>bold</b>" in main[0].html

    def test_display_data_separate_from_execute_result(self):
        ex = self.capsule.run_code(
            "from IPython.display import display, HTML\n"
            "display(HTML('<i>shown</i>'))\n"
            "'final'\n"
        )
        assert ex.error is None
        mains = [r for r in ex.results if r.is_main_result]
        displays = [r for r in ex.results if not r.is_main_result]
        assert len(mains) == 1
        assert mains[0].text == "'final'"
        assert len(displays) >= 1
        assert any(r.html and "shown" in r.html for r in displays)

    def test_matplotlib_png(self):
        ex = self.capsule.run_code(
            "%matplotlib inline\n"
            "import matplotlib.pyplot as plt\n"
            "plt.figure()\n"
            "plt.plot([1,2,3],[4,1,5])\n"
            "plt.show()\n"
        )
        if ex.error is not None and ex.error.name == "ModuleNotFoundError":
            pytest.skip("matplotlib not in template")
        assert ex.error is None
        pngs = [r for r in ex.results if r.png is not None]
        assert pngs, "expected at least one PNG result from plt.show()"

    def test_pandas_repr(self):
        ex = self.capsule.run_code(
            "import pandas as pd\npd.DataFrame({'a':[1,2],'b':[3,4]})\n"
        )
        if ex.error is not None and ex.error.name == "ModuleNotFoundError":
            pytest.skip("pandas not in template")
        assert ex.error is None
        main = [r for r in ex.results if r.is_main_result]
        assert main
        assert main[0].html is not None or main[0].text is not None

    def test_filesystem_round_trip(self):
        self.capsule.run_code(
            "with open('/tmp/from_kernel.txt','w') as f: f.write('written-by-kernel')"
        )
        content = self.capsule.files.read("/tmp/from_kernel.txt")
        assert content == "written-by-kernel"

    def test_text_preserves_string_repr(self):
        """Strings keep their surrounding quotes — the ``text/plain`` MIME
        is the Jupyter repr, which is what disambiguates ``'2'`` from
        ``2``."""
        ex = self.capsule.run_code("'hello'")
        assert ex.text == "'hello'"
        ex = self.capsule.run_code('"with\\"inside"')
        assert ex.text is not None
        assert ex.text.startswith("'") or ex.text.startswith('"')
        ex = self.capsule.run_code("42")
        assert ex.text == "42"
        ex = self.capsule.run_code("[1, 2, 3]")
        assert ex.text == "[1, 2, 3]"
        ex = self.capsule.run_code("{'k': 'v'}")
        assert ex.text == "{'k': 'v'}"

    def test_kernel_id_cached(self):
        first = self.capsule._kernel_id
        self.capsule.run_code("1")
        assert self.capsule._kernel_id == first

    def test_complex_workflow(self):
        ex = self.capsule.run_code(
            "import json\n"
            "data = [{'n': i, 'sq': i*i} for i in range(5)]\n"
            "print(json.dumps(data))\n"
            "sum(d['sq'] for d in data)\n"
        )
        assert ex.error is None
        assert ex.text == "30"
        assert any('"sq": 16' in c for c in ex.logs.stdout)


class TestCodeRunnerMimeTypes:
    """Cover every non-text MIME field on ``Result`` using the libs
    baked into the ``code-runner-beta`` template
    (numpy, pandas, matplotlib, seaborn, requests)."""

    capsule: Capsule

    @classmethod
    def setup_class(cls):
        _ensure_env()
        cls.capsule = Capsule(wait=True)

    @classmethod
    def teardown_class(cls):
        try:
            cls.capsule.destroy()
        except Exception:
            pass

    def _run(self, code: str) -> Execution:
        ex = self.capsule.run_code(code, timeout=60)
        assert ex.error is None, f"unexpected error: {ex.error}"
        return ex

    # ── html ──────────────────────────────────────────────────────
    def test_html_via_ipython_display(self):
        ex = self._run(
            "from IPython.display import HTML\nHTML('<table><tr><td>x</td></tr></table>')"
        )
        main = next(r for r in ex.results if r.is_main_result)
        assert main.html is not None
        assert "<table>" in main.html
        assert "html" in main.formats()

    def test_html_via_pandas_dataframe(self):
        ex = self._run(
            "import pandas as pd\n"
            "pd.DataFrame({'a': [1, 2, 3], 'b': ['x', 'y', 'z']})\n"
        )
        main = next(r for r in ex.results if r.is_main_result)
        assert main.html is not None
        # pandas emits a styled <table>
        assert "<table" in main.html
        assert "dataframe" in main.html.lower() or "<tr" in main.html
        # text/plain still present alongside html
        assert main.text is not None

    # ── markdown ──────────────────────────────────────────────────
    def test_markdown(self):
        ex = self._run(
            "from IPython.display import Markdown\nMarkdown('# heading\\n* a\\n* b')"
        )
        main = next(r for r in ex.results if r.is_main_result)
        assert main.markdown is not None
        assert "# heading" in main.markdown
        assert "markdown" in main.formats()

    # ── json ──────────────────────────────────────────────────────
    def test_json_bundle(self):
        ex = self._run(
            "from IPython.display import JSON\nJSON({'a': 1, 'nested': {'b': [1, 2]}})"
        )
        main = next(r for r in ex.results if r.is_main_result)
        # IPython.display.JSON emits application/json
        assert main.json is not None
        assert main.json == {"a": 1, "nested": {"b": [1, 2]}}
        assert "json" in main.formats()

    # ── latex ─────────────────────────────────────────────────────
    def test_latex(self):
        ex = self._run("from IPython.display import Latex\nLatex(r'$E = mc^2$')")
        main = next(r for r in ex.results if r.is_main_result)
        assert main.latex is not None
        assert "mc^2" in main.latex

    # ── svg ───────────────────────────────────────────────────────
    def test_svg(self):
        svg_payload = (
            '<svg xmlns=\\"http://www.w3.org/2000/svg\\" width=\\"10\\" height=\\"10\\">'
            '<rect width=\\"10\\" height=\\"10\\" fill=\\"red\\"/></svg>'
        )
        ex = self._run(f"from IPython.display import SVG\nSVG(data='{svg_payload}')")
        main = next(r for r in ex.results if r.is_main_result)
        assert main.svg is not None
        assert "<svg" in main.svg
        assert "<rect" in main.svg

    # ── javascript ────────────────────────────────────────────────
    def test_javascript(self):
        ex = self._run(
            "from IPython.display import Javascript\nJavascript('console.log(\"hi\")')"
        )
        main = next(r for r in ex.results if r.is_main_result)
        # Some IPython versions only emit text/plain for Javascript;
        # accept either javascript or extra/application/javascript.
        js = main.javascript or (main.extra or {}).get("application/javascript")
        assert js is not None, f"no js payload, got formats: {main.formats()}"
        assert "console.log" in js

    # ── png (matplotlib) ──────────────────────────────────────────
    def test_png_from_matplotlib(self):
        ex = self._run(
            "%matplotlib inline\n"
            "import matplotlib.pyplot as plt\n"
            "import numpy as np\n"
            "x = np.linspace(0, 6.28, 100)\n"
            "plt.figure()\n"
            "plt.plot(x, np.sin(x))\n"
            "plt.title('sine')\n"
            "plt.show()\n"
        )
        pngs = [r for r in ex.results if r.png is not None]
        assert pngs, "expected PNG from plt.show()"
        # Base64 PNG starts with iVBORw0KGgo (== PNG magic in base64)
        assert pngs[0].png.startswith("iVBORw0KGgo")
        assert "png" in pngs[0].formats()

    def test_png_from_seaborn(self):
        ex = self._run(
            "%matplotlib inline\n"
            "import matplotlib.pyplot as plt\n"
            "import seaborn as sns\n"
            "import pandas as pd\n"
            "df = pd.DataFrame({'x': [1, 2, 3, 4], 'y': [10, 20, 15, 25]})\n"
            "plt.figure()\n"
            "sns.barplot(data=df, x='x', y='y')\n"
            "plt.show()\n"
        )
        pngs = [r for r in ex.results if r.png is not None]
        assert pngs, "expected PNG from seaborn plot"
        assert pngs[0].png.startswith("iVBORw0KGgo")

    # ── jpeg ──────────────────────────────────────────────────────
    def test_jpeg_via_matplotlib(self):
        ex = self._run(
            "%matplotlib inline\n"
            "import matplotlib.pyplot as plt\n"
            "import matplotlib_inline.backend_inline as bi\n"
            "bi.set_matplotlib_formats('jpeg')\n"
            "plt.figure()\n"
            "plt.plot([1, 2, 3])\n"
            "plt.show()\n"
            "bi.set_matplotlib_formats('png')\n"
        )
        jpegs = [r for r in ex.results if r.jpeg is not None]
        if not jpegs:
            pytest.skip("matplotlib_inline jpeg backend unavailable")
        # JPEG magic in base64 starts with /9j/
        assert jpegs[0].jpeg.startswith("/9j/")

    # ── multi-format bundle ───────────────────────────────────────
    def test_pandas_emits_text_and_html(self):
        ex = self._run("import pandas as pd\npd.DataFrame({'n': range(3)})")
        main = next(r for r in ex.results if r.is_main_result)
        fmts = main.formats()
        assert "text" in fmts
        assert "html" in fmts
        assert main.is_main_result is True

    def test_matplotlib_figure_emits_png_and_text(self):
        ex = self._run(
            "%matplotlib inline\n"
            "import matplotlib.pyplot as plt\n"
            "fig, ax = plt.subplots()\n"
            "ax.plot([1, 2, 3])\n"
            "fig\n"  # return the figure as the last expression
        )
        main = next(r for r in ex.results if r.is_main_result)
        fmts = main.formats()
        # Figure repr bundles both text and png.
        assert "png" in fmts
        assert "text" in fmts

    # ── numpy / requests round-trips through .text ────────────────
    def test_numpy_array_text_repr(self):
        ex = self._run("import numpy as np\nnp.arange(5)")
        assert ex.text is not None
        assert "array([0, 1, 2, 3, 4])" in ex.text

    def test_requests_status_code(self):
        ex = self._run(
            "import requests\n"
            "r = requests.get('http://httpbingo.org/status/418', timeout=10)\n"
            "r.status_code\n"
        )
        assert ex.text == "418"


class TestCodeRunnerIsolation:
    """Each test gets its own capsule — verifies fresh-kernel boot."""

    def setup_method(self):
        _ensure_env()

    def test_fresh_capsule_no_state_leak(self):
        c1 = Capsule(wait=True)
        try:
            c1.run_code("leaked = 'c1'")
            c2 = Capsule(wait=True)
            try:
                ex = c2.run_code("leaked")
                assert ex.error is not None
                assert ex.error.name == "NameError"
            finally:
                c2.destroy()
        finally:
            c1.destroy()

    def test_context_manager(self):
        with Capsule(wait=True) as c:
            ex = c.run_code("'ctx'")
            assert ex.text == "'ctx'"

    def test_deprecated_code_interpreter_import_still_works(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            from wrenn.code_interpreter import Capsule as LegacyCapsule
        with LegacyCapsule(wait=True) as c:
            ex = c.run_code("'legacy'")
            assert ex.text == "'legacy'"


# ───────────────────────── Async e2e ─────────────────────────


class TestCodeRunnerAsync:
    def setup_method(self):
        _ensure_env()

    @pytest.mark.asyncio
    async def test_async_simple(self):
        async with await AsyncCapsule.create(wait=True) as c:
            ex = await c.run_code("21 * 2")
            assert ex.error is None
            assert ex.text == "42"

    @pytest.mark.asyncio
    async def test_async_persistence(self):
        async with await AsyncCapsule.create(wait=True) as c:
            await c.run_code("v = 'persisted'")
            ex = await c.run_code("v")
            assert ex.text == "'persisted'"

    @pytest.mark.asyncio
    async def test_async_callbacks(self):
        async with await AsyncCapsule.create(wait=True) as c:
            chunks: list[str] = []
            await c.run_code(
                "print('async out')",
                on_stdout=chunks.append,
            )
            assert any("async out" in s for s in chunks)

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        async with await AsyncCapsule.create(wait=True) as c:
            ex = await c.run_code("'in-ctx'")
            assert ex.text == "'in-ctx'"

    @pytest.mark.asyncio
    async def test_async_concurrent_capsules(self):
        async with await AsyncCapsule.create(wait=True) as c1:
            async with await AsyncCapsule.create(wait=True) as c2:
                r1, r2 = await asyncio.gather(
                    c1.run_code("1 + 1"),
                    c2.run_code("10 * 10"),
                )
                assert r1.text == "2"
                assert r2.text == "100"
