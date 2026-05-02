# AGENTS.md

## Project

Wrenn Python SDK — a client library for the Wrenn microVM platform. e2b drop-in replacement.
Package name: `wrenn`. Python 3.13+, managed with [uv](https://docs.astral.sh/uv/).

## Commands

```bash
uv sync                              # install deps
make lint                            # ruff check + format check (no auto-fix)
make test                            # unit tests only (tests/test_client.py)
make test-integration                # all tests including integration (needs live server)
make generate                        # regenerate models from OpenAPI spec (fetches from remote)
make check                           # lint + unit test
```

- `make test` only runs `tests/test_client.py`, not all unit tests. To run a specific test file: `uv run pytest tests/test_capsule_features.py -v`
- No typecheck step in Makefile or CI. `mypy` is a dev dependency but not wired up — do not assume it runs.

## Architecture

- `src/wrenn/` — the library package
  - `capsule.py` / `async_capsule.py` — high-level `Capsule` / `AsyncCapsule` (main user-facing classes)
  - `client.py` — low-level `WrennClient` / `AsyncWrennClient`
  - `commands.py` — command execution and streaming
  - `files.py` — filesystem operations
  - `pty.py` — interactive terminal (PTY) over WebSocket
  - `exceptions.py` — typed error hierarchy (`WrennError` base)
  - `models/_generated.py` — **auto-generated** from OpenAPI spec via `datamodel-codegen` (never edit directly; run `make generate`)
  - `sandbox.py` — deprecated `Sandbox` alias for `Capsule`
  - `code_interpreter/` — specialized capsule for stateful Jupyter kernel execution
- `tests/` — unit tests use `respx` to mock `httpx`; integration tests are in `tests/integration/`
- `api/openapi.yaml` — downloaded OpenAPI spec used for code generation

## Key Conventions

- Generated code lives in `src/wrenn/models/_generated.py`. Never edit it. Run `make generate` to update.
- `Sandbox` is a deprecated alias for `Capsule`. New code should use `Capsule` / `AsyncCapsule`.
- Dual sync/async API: every major class has an `Async` counterpart.
- Uses `httpx` for HTTP, `httpx-ws` for WebSockets, `pydantic` for models.
- `__init__.py` uses `__getattr__` for lazy deprecated aliases (`Sandbox`, `WrennHostHasSandboxesError`).

## Testing

- Unit tests mock HTTP via `respx` (httpx mocking library).
- Integration tests require env vars: `WRENN_API_KEY` (or `WRENN_TOKEN`), optionally `WRENN_BASE_URL`.
- Integration test fixtures in `tests/integration/conftest.py` create real capsules and clean them up.
- `pytest` marker: `@pytest.mark.integration` for tests needing a live server.

## CI

Woodpecker CI (`.woodpecker/check.yml`) runs on push to `main` and `dev`:
1. `make lint`
2. `make test` (unit tests only — integration tests are not in CI)
