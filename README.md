# Wrenn Python SDK

Python client for the [Wrenn](https://wrenn.dev) microVM platform. Create isolated capsules, execute commands, manage files, run interactive terminals, and execute persistent code -- all from Python.

Designed as a drop-in replacement for [e2b](https://e2b.dev). If you're migrating, just swap your imports.

## Installation

```bash
pip install wrenn
```

Requires Python 3.13+.

## Authentication

Set the `WRENN_API_KEY` environment variable:

```bash
export WRENN_API_KEY="wrn_your_api_key_here"
```

Optionally override the API base URL:

```bash
export WRENN_BASE_URL="https://app.wrenn.dev/api"  # default
```

You can also pass credentials directly:

```python
from wrenn import Capsule

capsule = Capsule(api_key="wrn_...", base_url="https://...")
```

---

## Wrenn Capsules

### Quick Start

```python
from wrenn import Capsule

# Create a capsule (reads WRENN_API_KEY from env)
with Capsule(template="minimal") as capsule:
    result = capsule.commands.run("echo hello")
    print(result.stdout)  # "hello\n"
```

### Creating Capsules

```python
from wrenn import Capsule

# Direct construction (creates immediately)
capsule = Capsule()
capsule = Capsule(template="base-python", vcpus=2, memory_mb=1024, timeout=300)

# With auto-wait (blocks until capsule is running)
capsule = Capsule(template="minimal", wait=True)

# Via factory classmethod
capsule = Capsule.create(template="minimal", wait=True)
```

### Context Manager

Use capsules as context managers for automatic cleanup (destroys capsule on exit):

```python
with Capsule(template="minimal", wait=True) as capsule:
    capsule.commands.run("echo hello")
# capsule is automatically destroyed
```

### Connecting to Existing Capsules

Attach to a running capsule by ID. If it's paused, it will be resumed automatically:

```python
capsule = Capsule.connect("cl-abc123")
result = capsule.commands.run("echo still running")
```

For code interpreter capsules:

```python
from wrenn.code_interpreter import Capsule as CodeCapsule

capsule = CodeCapsule.connect("cl-abc123")
result = capsule.run_code("print('reconnected')")
```

### Lifecycle Management

```python
# Instance methods
capsule.pause()
capsule.resume()
capsule.destroy()
capsule.ping()           # reset inactivity timer
capsule.wait_ready()     # block until running

info = capsule.get_info()
print(info.status)       # "running"
print(capsule.is_running())  # True

# Static methods (no instance needed)
Capsule.destroy("cl-abc123", api_key="wrn_...")
Capsule.pause("cl-abc123")
Capsule.resume("cl-abc123")
info = Capsule.get_info("cl-abc123")

# List all capsules
capsules = Capsule.list()
```

### Command Execution

Commands are accessed via `capsule.commands`:

```python
# Foreground (blocks until complete)
result = capsule.commands.run("python -c 'print(42)'")
print(result.stdout)       # "42\n"
print(result.stderr)       # ""
print(result.exit_code)    # 0
print(result.duration_ms)  # 35

# With options
result = capsule.commands.run(
    "python train.py",
    timeout=120,
    envs={"CUDA_VISIBLE_DEVICES": "0"},
    cwd="/app",
)

# Background process
handle = capsule.commands.run("python server.py", background=True)
print(handle.pid)  # 1234
print(handle.tag)  # "exec-abc123"
```

#### Streaming Output

```python
import sys

# Stream a new command
for event in capsule.commands.stream("python", args=["-u", "train.py"]):
    match event.type:
        case "stdout":
            print(event.data, end="")
        case "stderr":
            print(event.data, end="", file=sys.stderr)
        case "exit":
            print(f"\nExited with code {event.exit_code}")

# Connect to a running background process
for event in capsule.commands.connect(handle.pid):
    if event.type == "stdout":
        print(event.data, end="")
```

#### Process Management

```python
# List running processes
for proc in capsule.commands.list():
    print(proc.pid, proc.cmd, proc.tag)

# Kill a process
capsule.commands.kill(pid=1234)
```

### Filesystem

Files are accessed via `capsule.files`:

```python
# Write and read files
capsule.files.write("/app/main.py", "print('hello')")
content = capsule.files.read("/app/main.py")        # str
raw = capsule.files.read_bytes("/app/main.py")       # bytes

# Check existence
capsule.files.exists("/app/main.py")  # True

# List directory
entries = capsule.files.list("/home/user", depth=1)
for entry in entries:
    print(entry.name, entry.type, entry.size)

# Create directory
capsule.files.make_dir("/app/data")

# Remove file or directory
capsule.files.remove("/app/old_data")
```

#### Streaming (Large Files)

```python
# Streaming upload
def chunks():
    yield b"chunk1"
    yield b"chunk2"

capsule.files.upload_stream("/data/large.bin", chunks())

# Streaming download
for chunk in capsule.files.download_stream("/data/large.bin"):
    process(chunk)
```

### Git

Git operations are accessed via `capsule.git`. All commands execute the real `git` binary inside the capsule:

```python
# Initialize a repo
capsule.git.init("/app", initial_branch="main")

# Configure user
capsule.git.configure_user("Alice", "alice@example.com", cwd="/app")

# Stage and commit
capsule.git.add(all=True, cwd="/app")
capsule.git.commit("initial commit", cwd="/app")

# Check status
status = capsule.git.status(cwd="/app")
print(status.branch)    # "main"
print(status.is_clean)  # True
for f in status.files:
    print(f.path, f.index_status, f.work_tree_status)

# Branches
branches = capsule.git.branches(cwd="/app")
capsule.git.create_branch("feature", cwd="/app")
capsule.git.checkout_branch("main", cwd="/app")
capsule.git.delete_branch("feature", cwd="/app")
```

#### Clone with Authentication

```python
# Clone a private repo (credentials are stripped from remote URL after clone)
capsule.git.clone(
    "https://github.com/org/repo.git",
    username="user",
    password="ghp_token",
    cwd="/app",
)

# Push/pull with inline credentials (temporarily embedded, then restored)
capsule.git.push("origin", "main", username="user", password="ghp_token", cwd="/app")
capsule.git.pull("origin", "main", username="user", password="ghp_token", cwd="/app")
```

#### Configuration and Remotes

```python
capsule.git.set_config("core.autocrlf", "false", cwd="/app")
value = capsule.git.get_config("user.name", cwd="/app")  # str | None

capsule.git.remote_add("upstream", "https://github.com/org/repo.git", cwd="/app")
url = capsule.git.remote_get("origin", cwd="/app")  # str | None
```

Git errors raise `GitCommandError` (or `GitAuthError` for authentication failures), both inheriting from `GitError`:

```python
from wrenn import GitCommandError, GitAuthError

try:
    capsule.git.push("origin", "main", username="user", password="bad", cwd="/app")
except GitAuthError as e:
    print(e.stderr)
    print(e.exit_code)
```

### Interactive Terminal (PTY)

```python
import sys

with capsule.pty(cmd="/bin/bash", cols=120, rows=40, cwd="/home/user") as term:
    term.write(b"ls -la\n")
    for event in term:
        if event.type == "output":
            sys.stdout.buffer.write(event.data)
        elif event.type == "exit":
            break

# Reconnect to an existing session
with capsule.pty_connect(term.tag) as term:
    term.write(b"echo reconnected\n")
```

**PtySession methods:**

| Method | Description |
|--------|-------------|
| `write(data: bytes)` | Send raw bytes to stdin |
| `resize(cols, rows)` | Resize the terminal |
| `kill()` | Send SIGKILL to the process |
| `tag` | Session tag (after `started` event) |
| `pid` | Process PID (after `started` event) |

### Proxy URL

Access services running inside a capsule:

```python
url = capsule.get_url(8080)
# "wss://8080-cl-abc123.app.wrenn.dev"
```

### Snapshots

Create reusable templates from running capsules:

```python
template = capsule.create_snapshot(name="my-template", overwrite=True)
```

---

## Code Interpreter

The `wrenn.code_interpreter` module provides a specialized capsule for stateful code execution via a persistent Jupyter kernel.

### Quick Start

```python
from wrenn.code_interpreter import Capsule

with Capsule(wait=True) as capsule:
    result = capsule.run_code("print('hello')")
    print("".join(result.logs.stdout))  # "hello\n"
```

### Stateful Execution

Variables, imports, and function definitions persist across `run_code` calls:

```python
from wrenn.code_interpreter import Capsule

with Capsule(wait=True) as capsule:
    capsule.run_code("x = 42")
    result = capsule.run_code("x * 2")
    print(result.text)  # "84"

    capsule.run_code("import math")
    result = capsule.run_code("math.pi")
    print(result.text)  # "3.141592653589793"

    capsule.run_code("def greet(name): return f'hello {name}'")
    result = capsule.run_code("greet('world')")
    print(result.text)  # "hello world"
```

The `text` property returns the `text/plain` value of the main `execute_result` (the last expression in the cell). Printed output goes to `result.logs.stdout` instead.

### Error Handling in Code

```python
result = capsule.run_code("1 / 0")
print(result.error.name)       # "ZeroDivisionError"
print(result.error.value)      # "division by zero"
print(result.error.traceback)  # full traceback string
```

### Rich Output

Each call to `display()`, `plt.show()`, or similar produces a `Result` in `execution.results`. Known MIME types are unpacked into named fields:

```python
result = capsule.run_code("""
import matplotlib.pyplot as plt
plt.plot([1, 2, 3])
plt.show()
""")
for r in result.results:
    if r.png:
        print(f"Got PNG image ({len(r.png)} bytes base64)")
    print(r.formats())  # e.g. ["text", "png"]
```

### Streaming Callbacks

```python
capsule.run_code(
    code,
    on_result=lambda r: print("result:", r.formats()),
    on_stdout=lambda text: print("stdout:", text),
    on_stderr=lambda text: print("stderr:", text),
    on_error=lambda err: print(f"error: {err.name}: {err.value}"),
)
```

### Custom Templates

By default, `code-runner-beta` template is used. You can specify a custom template:

```python
capsule = Capsule(template="my-custom-jupyter-template", wait=True)
result = capsule.run_code("print('running on custom template')")
```

### Execution Model

`run_code()` returns an `Execution` object:

| Field | Type | Description |
|-------|------|-------------|
| `results` | `list[Result]` | All rich outputs (charts, images, expression values) |
| `logs` | `Logs` | `.stdout: list[str]` and `.stderr: list[str]` chunks |
| `error` | `ExecutionError \| None` | `.name`, `.value`, `.traceback` |
| `execution_count` | `int \| None` | Jupyter cell execution counter |
| `text` | `str \| None` | (property) `text/plain` of the main `execute_result` |

Each `Result` has typed MIME fields: `text`, `html`, `markdown`, `svg`, `png`, `jpeg`, `pdf`, `latex`, `json`, `javascript`, plus `extra` for unknown types. String expression results have quotes stripped automatically.

### Code Interpreter + Commands/Files

The code interpreter capsule inherits all standard capsule features:

```python
from wrenn.code_interpreter import Capsule

with Capsule(wait=True) as capsule:
    # Use run_code for Jupyter execution
    capsule.run_code("import pandas as pd; df = pd.DataFrame({'a': [1,2,3]})")
    capsule.run_code("df.to_csv('/tmp/data.csv', index=False)")

    # Use standard file operations
    content = capsule.files.read("/tmp/data.csv")
    print(content)

    # Use standard command execution
    result = capsule.commands.run("wc -l /tmp/data.csv")
    print(result.stdout)
```

---

## Async Support

All operations have async variants via `AsyncCapsule`:

### Async Capsule

```python
from wrenn import AsyncCapsule

async with await AsyncCapsule.create(template="minimal", wait=True) as capsule:
    result = await capsule.commands.run("echo hello")
    print(result.stdout)

    await capsule.files.write("/app/file.txt", "data")
    entries = await capsule.files.list("/app")

    await capsule.pause()
    await capsule.resume()
```

### Async Code Interpreter

```python
from wrenn.code_interpreter import AsyncCapsule

async with await AsyncCapsule.create(wait=True) as capsule:
    result = await capsule.run_code("2 + 2")
    print(result.text)  # "4"
```

### Async PTY

```python
async with capsule.pty(cmd="/bin/bash") as term:
    await term.write(b"ls -la\n")
    async for event in term:
        if event.type == "output":
            sys.stdout.buffer.write(event.data)
```

---

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
    WrennHostHasCapsulesError, # 409 (host has running capsules)
    WrennAgentError,           # 502
    WrennInternalError,        # 500
    WrennHostUnavailableError, # 503
)

try:
    Capsule.get_info("nonexistent")
except WrennNotFoundError as e:
    print(e.code)         # "not_found"
    print(e.message)      # "capsule not found"
    print(e.status_code)  # 404
```

All exceptions inherit from `WrennError` and expose `.code`, `.message`, and `.status_code`.

---

## Migrating from e2b

Replace your imports:

```python
# Before
from e2b import Sandbox
sandbox = Sandbox()

# After
from wrenn import Capsule
capsule = Capsule()
```

For code interpreter:

```python
# Before
from e2b_code_interpreter import Sandbox
sandbox = Sandbox()
result = sandbox.run_code("print('hello')")

# After
from wrenn.code_interpreter import Capsule
capsule = Capsule()
result = capsule.run_code("print('hello')")
```

The `Sandbox` name is available as a deprecated alias in both modules:

```python
from wrenn import Sandbox                    # works, emits FutureWarning
from wrenn.code_interpreter import Sandbox   # works, emits FutureWarning
```

---

## Low-Level Client

For direct API access, use `WrennClient` / `AsyncWrennClient`:

```python
from wrenn import WrennClient

with WrennClient(api_key="wrn_...") as client:
    capsule = client.capsules.create(template="minimal")
    client.capsules.pause(capsule.id)
    client.capsules.resume(capsule.id)
    client.capsules.ping(capsule.id)
    client.capsules.destroy(capsule.id)

    # Snapshots
    template = client.snapshots.create(capsule_id="cl-abc", name="my-snap")
    templates = client.snapshots.list()
    client.snapshots.delete("my-snap")
```

---

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
```

### Running Integration Tests

Integration tests require a live Wrenn server. Set credentials via environment or a `.env` file at the project root:

```bash
# Option 1: environment variable
export WRENN_API_KEY="wrn_..."

# Option 2: .env file
echo 'WRENN_API_KEY=wrn_...' > .env
```

Then run:

```bash
make test-integration
```

Tests are automatically skipped when `WRENN_API_KEY` is not available.

## License

MIT
