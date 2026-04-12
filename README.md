# Wrenn Python SDK

Python client for the [Wrenn](https://wrenn.dev) microVM code execution platform. Create isolated capsules, execute commands, manage files, run interactive terminals, and execute persistent code — all from Python.

## Installation

```bash
pip install wrenn
```

Requires Python 3.13+.

## Quick Start

```python
from wrenn import WrennClient

client = WrennClient(api_key="wrn_your_api_key_here")

# Create a capsule and run a command
with client.capsules.create(template="minimal", timeout_sec=120) as cap:
    cap.wait_ready(timeout=60)

    result = cap.exec("echo", args=["hello world"])
    print(result.stdout)     # "hello world"
    print(result.exit_code)  # 0
```

## Authentication

The SDK supports two authentication methods:

```python
# API key
client = WrennClient(api_key="wrn_...")

# JWT token
client = WrennClient(token="eyJ...")
```

You can obtain an API key via the dashboard or create one programmatically:

```python
with WrennClient(token="jwt_token") as client:
    key = client.api_keys.create(name="my-key")
    print(key.key)  # wrn_...
```

## Capsules

Capsules are isolated microVM environments. Create, manage, and interact with them:

```python
# Create
cap = client.capsules.create(
    template="base-python",
    vcpus=2,
    memory_mb=1024,
    timeout_sec=300,
)

# List
for c in client.capsules.list():
    print(c.id, c.status)

# Get
cap = client.capsules.get("cl-abc123")

# Destroy
client.capsules.destroy("cl-abc123")
```

### Context Manager

Use capsules as context managers for automatic cleanup:

```python
with client.capsules.create(template="minimal", timeout_sec=120) as cap:
    cap.wait_ready(timeout=60)
    cap.exec("python -c 'print(42)'")
# cap.destroy() is called automatically
```

## Command Execution

### `exec()` — One-off Commands

Starts a fresh process for each call. No state persists between calls.

```python
result = cap.exec("python", args=["-c", "import os; print(os.getcwd())"])
print(result.stdout)     # "/home/user\n"
print(result.stderr)     # ""
print(result.exit_code)  # 0
print(result.duration_ms)  # 42
```

### `exec_stream()` — Streaming Output

Stream real-time output from long-running commands:

```python
for event in cap.exec_stream("python", args=["-u", "train.py"]):
    match event.type:
        case "stdout":
            print(event.data, end="")
        case "stderr":
            print(event.data, end="", file=sys.stderr)
        case "exit":
            print(f"\nExited with code {event.exit_code}")
```

### `run_code()` — Stateful Code Execution

Execute Python code in a persistent Jupyter kernel. Variables, imports, and function definitions survive across calls:

```python
with client.capsules.create(template="python-interpreter-v0-beta") as cap:
    cap.wait_ready(timeout=60)

    cap.run_code("x = 42")
    r = cap.run_code("x * 2")
    print(r.text)  # "84"

    cap.run_code("def greet(name): return f'hello {name}'")
    r = cap.run_code("greet('world')")
    print(r.text)  # "'hello world'"

    r = cap.run_code("1/0")
    print(r.error)  # "ZeroDivisionError: division by zero\n..."
```

**`CodeResult` fields:**

| Field | Type | Description |
|-------|------|-------------|
| `text` | `str \| None` | Plain text representation |
| `data` | `dict \| None` | Rich MIME bundle (e.g. `{"image/png": "..."}`) |
| `stdout` | `str` | Accumulated stdout |
| `stderr` | `str` | Accumulated stderr |
| `error` | `str \| None` | Error traceback string |

## Filesystem

Upload, download, and manage files inside capsules:

```python
# Upload / Download
cap.upload("/app/main.py", b"print('hello')")
content = cap.download("/app/main.py")

# Streaming (for large files)
def chunks():
    yield b"chunk1"
    yield b"chunk2"

cap.stream_upload("/data/large.bin", chunks())
for chunk in cap.stream_download("/data/large.bin"):
    process(chunk)

# Directory operations
entries = cap.list_dir("/home/user", depth=1)
for entry in entries:
    print(entry.name, entry.type, entry.size)

cap.mkdir("/home/user/data")
cap.remove("/home/user/old_data")
```

## Interactive Terminal (PTY)

Open a full interactive terminal session over WebSocket:

```python
with cap.pty(cmd="/bin/bash", cols=120, rows=40, cwd="/home/user") as term:
    term.write(b"ls -la\n")
    for event in term:
        if event.type == "output":
            sys.stdout.buffer.write(event.data)
        elif event.type == "exit":
            break
```

**PtySession methods:**

| Method | Description |
|--------|-------------|
| `write(data: bytes)` | Send raw bytes to stdin |
| `resize(cols, rows)` | Resize the terminal |
| `kill()` | Send SIGKILL to the process |
| `tag` | Session tag (available after `started` event) |
| `pid` | Process PID (available after `started` event) |

Reconnect to an existing session using the tag:

```python
with cap.pty_connect(term.tag) as term:
    term.write(b"echo reconnected\n")
```

## Lifecycle

Pause and resume capsules to save resources:

```python
cap = client.capsules.create(template="minimal")
cap.wait_ready(timeout=60)

# Pause (snapshots and releases resources)
cap.pause()
print(cap.status)  # "paused"

# Resume (restores from snapshot)
cap.resume()
cap.wait_ready(timeout=60)
```

Keep a capsule alive with `ping()`:

```python
cap.ping()  # Resets the inactivity timer
```

## Proxy URL

Access services running inside a capsule through the proxy:

```python
url = cap.get_url(8888)
# "wss://8888-cl-abc123.api.wrenn.dev"

# Pre-configured HTTP client targeting port 8888
resp = cap.http_client.get("/api/kernels")
```

## Snapshots

Create templates from running capsules:

```python
# Create a snapshot
template = client.snapshots.create(
    capsule_id="cl-abc123",
    name="my-template",
    overwrite=True,
)

# List templates
for t in client.snapshots.list():
    print(t.name, t.type)

# Delete
client.snapshots.delete("my-template")
```

## Hosts

Manage host machines:

```python
host = client.hosts.create(type="regular")
client.hosts.list()
client.hosts.get("h-1")
client.hosts.delete("h-1")
client.hosts.regenerate_token("h-1")
client.hosts.list_tags("h-1")
client.hosts.add_tag("h-1", "gpu")
client.hosts.remove_tag("h-1", "gpu")
```

## Async Support

All operations have async variants. Use `AsyncWrennClient` and prefix capsule methods with `async_`:

```python
from wrenn import AsyncWrennClient

async with AsyncWrennClient(api_key="wrn_...") as client:
    cap = await client.capsules.create(template="minimal")
    await cap.async_wait_ready(timeout=60)

    result = await cap.async_exec("echo", args=["hello"])
    await cap.async_upload("/app/file.txt", b"data")
    entries = await cap.async_list_dir("/home/user")
    r = await cap.async_run_code("42 * 2")

    await cap.async_destroy()
```

**Async method mapping:**

| Sync | Async |
|------|-------|
| `exec()` | `async_exec()` |
| `upload()` | `async_upload()` |
| `download()` | `async_download()` |
| `stream_upload()` | `async_stream_upload()` |
| `stream_download()` | `async_stream_download()` |
| `list_dir()` | `async_list_dir()` |
| `mkdir()` | `async_mkdir()` |
| `remove()` | `async_remove()` |
| `wait_ready()` | `async_wait_ready()` |
| `pause()` | `async_pause()` |
| `resume()` | `async_resume()` |
| `destroy()` | `async_destroy()` |
| `ping()` | `async_ping()` |
| `run_code()` | `async_run_code()` |

## Error Handling

The SDK maps server error codes to typed exceptions:

```python
from wrenn import (
    WrennError,
    WrennValidationError,      # 400
    WrennAuthenticationError,  # 401
    WrennForbiddenError,       # 403
    WrennNotFoundError,        # 404
    WrennConflictError,        # 409
    WrennHostHasCapsulesError, # 409 — host has running capsules
    WrennAgentError,           # 502
    WrennInternalError,        # 500
    WrennHostUnavailableError, # 503
)

try:
    client.capsules.get("nonexistent")
except WrennNotFoundError as e:
    print(e.code)         # "not_found"
    print(e.message)      # "capsule not found"
    print(e.status_code)  # 404
```

All exceptions inherit from `WrennError` and expose `.code`, `.message`, and `.status_code`.

## Development

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
# Install dependencies
uv sync

# Run linting
make lint

# Run unit tests
make test

# Run all tests (including integration)
make test-integration

# Regenerate models from OpenAPI spec
make generate
```

### Running Integration Tests

Integration tests require a live Wrenn server. Set environment variables:

```bash
export WRENN_API_KEY="wrn_..."
export WRENN_BASE_URL="http://localhost:8080"  # optional
make test-integration
```

## License

MIT
