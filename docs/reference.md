<a id="wrenn"></a>

# wrenn

<a id="wrenn.client"></a>

# wrenn.client

<a id="wrenn.client.CapsulesResource"></a>

## CapsulesResource Objects

```python
class CapsulesResource()
```

Sync capsule control-plane operations.

<a id="wrenn.client.CapsulesResource.create"></a>

#### create

```python
def create(template: str | None = None,
           vcpus: int | None = None,
           memory_mb: int | None = None,
           timeout_sec: int | None = None) -> CapsuleModel
```

Create a new capsule.

**Arguments**:

- `template` _str | None_ - Template name to boot from.
- `vcpus` _int | None_ - Number of virtual CPUs.
- `memory_mb` _int | None_ - Memory in MiB.
- `timeout_sec` _int | None_ - Inactivity TTL in seconds before
  auto-pause. ``0`` disables auto-pause.
  

**Returns**:

- `CapsuleModel` - The newly created capsule.

<a id="wrenn.client.CapsulesResource.list"></a>

#### list

```python
def list() -> list[CapsuleModel]
```

List all capsules for the authenticated team.

**Returns**:

- `list[CapsuleModel]` - All capsules belonging to the team.

<a id="wrenn.client.CapsulesResource.get"></a>

#### get

```python
def get(id: str) -> CapsuleModel
```

Get a capsule by ID.

**Arguments**:

- `id` _str_ - Capsule ID.
  

**Returns**:

- `CapsuleModel` - Current state of the capsule.
  

**Raises**:

- `WrennNotFoundError` - If no capsule with the given ID exists.

<a id="wrenn.client.CapsulesResource.destroy"></a>

#### destroy

```python
def destroy(id: str) -> None
```

Destroy a capsule permanently.

**Arguments**:

- `id` _str_ - Capsule ID.
  

**Raises**:

- `WrennNotFoundError` - If no capsule with the given ID exists.

<a id="wrenn.client.CapsulesResource.pause"></a>

#### pause

```python
def pause(id: str) -> CapsuleModel
```

Pause a running capsule.

**Arguments**:

- `id` _str_ - Capsule ID.
  

**Returns**:

- `CapsuleModel` - Updated capsule state.
  

**Raises**:

- `WrennNotFoundError` - If no capsule with the given ID exists.

<a id="wrenn.client.CapsulesResource.resume"></a>

#### resume

```python
def resume(id: str) -> CapsuleModel
```

Resume a paused capsule.

**Arguments**:

- `id` _str_ - Capsule ID.
  

**Returns**:

- `CapsuleModel` - Updated capsule state.
  

**Raises**:

- `WrennNotFoundError` - If no capsule with the given ID exists.

<a id="wrenn.client.CapsulesResource.ping"></a>

#### ping

```python
def ping(id: str) -> None
```

Reset the inactivity timer for a capsule.

**Arguments**:

- `id` _str_ - Capsule ID.
  

**Raises**:

- `WrennNotFoundError` - If no capsule with the given ID exists.

<a id="wrenn.client.AsyncCapsulesResource"></a>

## AsyncCapsulesResource Objects

```python
class AsyncCapsulesResource()
```

Async capsule control-plane operations.

<a id="wrenn.client.AsyncCapsulesResource.create"></a>

#### create

```python
async def create(template: str | None = None,
                 vcpus: int | None = None,
                 memory_mb: int | None = None,
                 timeout_sec: int | None = None) -> CapsuleModel
```

Create a new capsule.

**Arguments**:

- `template` _str | None_ - Template name to boot from.
- `vcpus` _int | None_ - Number of virtual CPUs.
- `memory_mb` _int | None_ - Memory in MiB.
- `timeout_sec` _int | None_ - Inactivity TTL in seconds before
  auto-pause. ``0`` disables auto-pause.
  

**Returns**:

- `CapsuleModel` - The newly created capsule.

<a id="wrenn.client.AsyncCapsulesResource.list"></a>

#### list

```python
async def list() -> list[CapsuleModel]
```

List all capsules for the authenticated team.

**Returns**:

- `list[CapsuleModel]` - All capsules belonging to the team.

<a id="wrenn.client.AsyncCapsulesResource.get"></a>

#### get

```python
async def get(id: str) -> CapsuleModel
```

Get a capsule by ID.

**Arguments**:

- `id` _str_ - Capsule ID.
  

**Returns**:

- `CapsuleModel` - Current state of the capsule.
  

**Raises**:

- `WrennNotFoundError` - If no capsule with the given ID exists.

<a id="wrenn.client.AsyncCapsulesResource.destroy"></a>

#### destroy

```python
async def destroy(id: str) -> None
```

Destroy a capsule permanently.

**Arguments**:

- `id` _str_ - Capsule ID.
  

**Raises**:

- `WrennNotFoundError` - If no capsule with the given ID exists.

<a id="wrenn.client.AsyncCapsulesResource.pause"></a>

#### pause

```python
async def pause(id: str) -> CapsuleModel
```

Pause a running capsule.

**Arguments**:

- `id` _str_ - Capsule ID.
  

**Returns**:

- `CapsuleModel` - Updated capsule state.
  

**Raises**:

- `WrennNotFoundError` - If no capsule with the given ID exists.

<a id="wrenn.client.AsyncCapsulesResource.resume"></a>

#### resume

```python
async def resume(id: str) -> CapsuleModel
```

Resume a paused capsule.

**Arguments**:

- `id` _str_ - Capsule ID.
  

**Returns**:

- `CapsuleModel` - Updated capsule state.
  

**Raises**:

- `WrennNotFoundError` - If no capsule with the given ID exists.

<a id="wrenn.client.AsyncCapsulesResource.ping"></a>

#### ping

```python
async def ping(id: str) -> None
```

Reset the inactivity timer for a capsule.

**Arguments**:

- `id` _str_ - Capsule ID.
  

**Raises**:

- `WrennNotFoundError` - If no capsule with the given ID exists.

<a id="wrenn.client.SnapshotsResource"></a>

## SnapshotsResource Objects

```python
class SnapshotsResource()
```

Sync snapshot operations.

<a id="wrenn.client.SnapshotsResource.create"></a>

#### create

```python
def create(capsule_id: str,
           name: str | None = None,
           overwrite: bool = False) -> Template
```

Create a snapshot template from a running capsule.

**Arguments**:

- `capsule_id` _str_ - ID of the capsule to snapshot.
- `name` _str | None_ - Name for the snapshot template. Auto-generated
  if not provided.
- `overwrite` _bool_ - If ``True``, overwrite an existing template with
  the same name. Defaults to ``False``.
  

**Returns**:

- `Template` - The created snapshot template.

<a id="wrenn.client.SnapshotsResource.list"></a>

#### list

```python
def list(type: str | None = None) -> list[Template]
```

List snapshot templates.

**Arguments**:

- `type` _str | None_ - Filter by template type. Returns all templates
  if not provided.
  

**Returns**:

- `list[Template]` - Matching snapshot templates.

<a id="wrenn.client.SnapshotsResource.delete"></a>

#### delete

```python
def delete(name: str) -> None
```

Delete a snapshot template by name.

**Arguments**:

- `name` _str_ - Template name to delete.
  

**Raises**:

- `WrennNotFoundError` - If no template with the given name exists.

<a id="wrenn.client.AsyncSnapshotsResource"></a>

## AsyncSnapshotsResource Objects

```python
class AsyncSnapshotsResource()
```

Async snapshot operations.

<a id="wrenn.client.AsyncSnapshotsResource.create"></a>

#### create

```python
async def create(capsule_id: str,
                 name: str | None = None,
                 overwrite: bool = False) -> Template
```

Create a snapshot template from a running capsule.

**Arguments**:

- `capsule_id` _str_ - ID of the capsule to snapshot.
- `name` _str | None_ - Name for the snapshot template. Auto-generated
  if not provided.
- `overwrite` _bool_ - If ``True``, overwrite an existing template with
  the same name. Defaults to ``False``.
  

**Returns**:

- `Template` - The created snapshot template.

<a id="wrenn.client.AsyncSnapshotsResource.list"></a>

#### list

```python
async def list(type: str | None = None) -> list[Template]
```

List snapshot templates.

**Arguments**:

- `type` _str | None_ - Filter by template type. Returns all templates
  if not provided.
  

**Returns**:

- `list[Template]` - Matching snapshot templates.

<a id="wrenn.client.AsyncSnapshotsResource.delete"></a>

#### delete

```python
async def delete(name: str) -> None
```

Delete a snapshot template by name.

**Arguments**:

- `name` _str_ - Template name to delete.
  

**Raises**:

- `WrennNotFoundError` - If no template with the given name exists.

<a id="wrenn.client.WrennClient"></a>

## WrennClient Objects

```python
class WrennClient()
```

Synchronous client for the Wrenn API.

Authenticates with an API key.

**Arguments**:

- `api_key` - API key (``wrn_...``). Falls back to ``WRENN_API_KEY`` env var.
- `base_url` - Wrenn API base URL.

<a id="wrenn.client.WrennClient.http"></a>

#### http

```python
@property
def http() -> httpx.Client
```

The underlying httpx.Client (for sub-objects that need direct access).

<a id="wrenn.client.WrennClient.close"></a>

#### close

```python
def close() -> None
```

Close the underlying HTTP connection pool.

<a id="wrenn.client.AsyncWrennClient"></a>

## AsyncWrennClient Objects

```python
class AsyncWrennClient()
```

Asynchronous client for the Wrenn API.

Authenticates with an API key.

**Arguments**:

- `api_key` - API key (``wrn_...``). Falls back to ``WRENN_API_KEY`` env var.
- `base_url` - Wrenn API base URL. Falls back to ``WRENN_BASE_URL`` env var.

<a id="wrenn.client.AsyncWrennClient.http"></a>

#### http

```python
@property
def http() -> httpx.AsyncClient
```

The underlying httpx.AsyncClient.

<a id="wrenn.client.AsyncWrennClient.aclose"></a>

#### aclose

```python
async def aclose() -> None
```

Close the underlying async HTTP connection pool.

<a id="wrenn.sandbox"></a>

# wrenn.sandbox

<a id="wrenn.commands"></a>

# wrenn.commands

<a id="wrenn.commands.CommandResult"></a>

## CommandResult Objects

```python
@dataclass
class CommandResult()
```

Result from a foreground command execution.

<a id="wrenn.commands.CommandHandle"></a>

## CommandHandle Objects

```python
@dataclass
class CommandHandle()
```

Handle for a background process.

<a id="wrenn.commands.ProcessInfo"></a>

## ProcessInfo Objects

```python
@dataclass
class ProcessInfo()
```

Information about a running process.

<a id="wrenn.commands.StreamEvent"></a>

## StreamEvent Objects

```python
class StreamEvent()
```

Base class for streaming exec events.

<a id="wrenn.commands.Commands"></a>

## Commands Objects

```python
class Commands()
```

Sync command execution interface. Accessed via ``capsule.commands``.

<a id="wrenn.commands.Commands.run"></a>

#### run

```python
def run(cmd: str,
        *,
        background: bool = False,
        timeout: int | None = 30,
        envs: dict[str, str] | None = None,
        cwd: str | None = None,
        tag: str | None = None) -> CommandResult | CommandHandle
```

Execute a shell command inside the capsule.

**Arguments**:

- `cmd` _str_ - Shell command string to execute.
- `background` _bool_ - If ``True``, launch the process in the
  background and return a :class:`CommandHandle` immediately.
  Defaults to ``False``.
- `timeout` _int | None_ - Seconds before the foreground command times
  out. Ignored for background commands. Defaults to ``30``.
- `envs` _dict[str, str] | None_ - Additional environment variables
  to set for the process.
- `cwd` _str | None_ - Working directory for the process.
- `tag` _str | None_ - Optional label attached to background processes
  for later retrieval via :meth:`connect`.
  

**Returns**:

- `CommandResult` - stdout, stderr, exit code, and duration for
  foreground commands (``background=False``).
  
- `CommandHandle` - PID and tag for background commands
  (``background=True``).

<a id="wrenn.commands.Commands.list"></a>

#### list

```python
def list() -> list[ProcessInfo]
```

List all running background processes in the capsule.

**Returns**:

- `list[ProcessInfo]` - Running processes with their PID, tag, and
  command information.

<a id="wrenn.commands.Commands.kill"></a>

#### kill

```python
def kill(pid: int) -> None
```

Send SIGKILL to a background process.

**Arguments**:

- `pid` _int_ - PID of the process to kill.
  

**Raises**:

- `WrennNotFoundError` - If no process with the given PID exists.

<a id="wrenn.commands.Commands.connect"></a>

#### connect

```python
def connect(pid: int) -> Iterator[StreamEvent]
```

Connect to a running background process and stream its output.

**Arguments**:

- `pid` _int_ - PID of the background process to attach to.
  

**Yields**:

- `StreamEvent` - Successive output events. Stops on
  :class:`StreamExitEvent` or :class:`StreamErrorEvent`.

<a id="wrenn.commands.Commands.stream"></a>

#### stream

```python
def stream(cmd: str, args: list[str] | None = None) -> Iterator[StreamEvent]
```

Execute a command via WebSocket, streaming output as events.

**Arguments**:

- `cmd` _str_ - Command to execute.
- `args` _list[str] | None_ - Additional arguments for the command.
  When omitted, *cmd* is interpreted as a shell command
  string and executed via ``/bin/sh -c``.
  

**Yields**:

- `StreamEvent` - Successive events including :class:`StreamStartEvent`,
  :class:`StreamStdoutEvent`, :class:`StreamStderrEvent`,
  :class:`StreamExitEvent`, and :class:`StreamErrorEvent`.

<a id="wrenn.commands.AsyncCommands"></a>

## AsyncCommands Objects

```python
class AsyncCommands()
```

Async command execution interface. Accessed via ``capsule.commands``.

<a id="wrenn.commands.AsyncCommands.run"></a>

#### run

```python
async def run(cmd: str,
              *,
              background: bool = False,
              timeout: int | None = 30,
              envs: dict[str, str] | None = None,
              cwd: str | None = None,
              tag: str | None = None) -> CommandResult | CommandHandle
```

Execute a shell command inside the capsule.

**Arguments**:

- `cmd` _str_ - Shell command string to execute.
- `background` _bool_ - If ``True``, launch the process in the
  background and return a :class:`CommandHandle` immediately.
  Defaults to ``False``.
- `timeout` _int | None_ - Seconds before the foreground command times
  out. Ignored for background commands. Defaults to ``30``.
- `envs` _dict[str, str] | None_ - Additional environment variables
  to set for the process.
- `cwd` _str | None_ - Working directory for the process.
- `tag` _str | None_ - Optional label attached to background processes
  for later retrieval via :meth:`connect`.
  

**Returns**:

- `CommandResult` - stdout, stderr, exit code, and duration for
  foreground commands (``background=False``).
  
- `CommandHandle` - PID and tag for background commands
  (``background=True``).

<a id="wrenn.commands.AsyncCommands.list"></a>

#### list

```python
async def list() -> list[ProcessInfo]
```

List all running background processes in the capsule.

**Returns**:

- `list[ProcessInfo]` - Running processes with their PID, tag, and
  command information.

<a id="wrenn.commands.AsyncCommands.kill"></a>

#### kill

```python
async def kill(pid: int) -> None
```

Send SIGKILL to a background process.

**Arguments**:

- `pid` _int_ - PID of the process to kill.
  

**Raises**:

- `WrennNotFoundError` - If no process with the given PID exists.

<a id="wrenn.commands.AsyncCommands.connect"></a>

#### connect

```python
async def connect(pid: int) -> AsyncIterator[StreamEvent]
```

Connect to a running background process and stream its output.

**Arguments**:

- `pid` _int_ - PID of the background process to attach to.
  

**Yields**:

- `StreamEvent` - Successive output events. Stops on
  :class:`StreamExitEvent` or :class:`StreamErrorEvent`.

<a id="wrenn.commands.AsyncCommands.stream"></a>

#### stream

```python
async def stream(cmd: str,
                 args: list[str] | None = None) -> AsyncIterator[StreamEvent]
```

Execute a command via WebSocket, streaming output as events.

**Arguments**:

- `cmd` _str_ - Command to execute.
- `args` _list[str] | None_ - Additional arguments for the command.
  When omitted, *cmd* is interpreted as a shell command
  string and executed via ``/bin/sh -c``.
  

**Yields**:

- `StreamEvent` - Successive events including :class:`StreamStartEvent`,
  :class:`StreamStdoutEvent`, :class:`StreamStderrEvent`,
  :class:`StreamExitEvent`, and :class:`StreamErrorEvent`.

<a id="wrenn.files"></a>

# wrenn.files

<a id="wrenn.files.Files"></a>

## Files Objects

```python
class Files()
```

Sync filesystem interface. Accessed via ``capsule.files``.

<a id="wrenn.files.Files.read"></a>

#### read

```python
def read(path: str) -> str
```

Read a file as a UTF-8 string.

**Arguments**:

- `path` _str_ - Absolute path to the file inside the capsule.
  

**Returns**:

- `str` - File contents decoded as UTF-8.
  

**Raises**:

- `WrennNotFoundError` - If the path does not exist.

<a id="wrenn.files.Files.read_bytes"></a>

#### read\_bytes

```python
def read_bytes(path: str) -> bytes
```

Read a file as raw bytes.

**Arguments**:

- `path` _str_ - Absolute path to the file inside the capsule.
  

**Returns**:

- `bytes` - Raw file contents.
  

**Raises**:

- `WrennNotFoundError` - If the path does not exist.

<a id="wrenn.files.Files.write"></a>

#### write

```python
def write(path: str, data: str | bytes) -> None
```

Write data to a file inside the capsule.

Creates parent directories if they do not exist.

**Arguments**:

- `path` _str_ - Absolute destination path inside the capsule.
- `data` _str | bytes_ - Content to write. Strings are UTF-8 encoded.

<a id="wrenn.files.Files.list"></a>

#### list

```python
def list(path: str, depth: int = 1) -> list[FileEntry]
```

List directory contents.

**Arguments**:

- `path` _str_ - Absolute path to the directory inside the capsule.
- `depth` _int_ - Recursion depth. ``1`` lists only immediate children.
  Defaults to ``1``.
  

**Returns**:

- `list[FileEntry]` - Entries in the directory.
  

**Raises**:

- `WrennNotFoundError` - If the path does not exist.

<a id="wrenn.files.Files.exists"></a>

#### exists

```python
def exists(path: str) -> bool
```

Check whether a path exists inside the capsule.

**Arguments**:

- `path` _str_ - Absolute path to check.
  

**Returns**:

- `bool` - ``True`` if the path exists.

<a id="wrenn.files.Files.make_dir"></a>

#### make\_dir

```python
def make_dir(path: str) -> FileEntry
```

Create a directory (with parents). Idempotent.

**Arguments**:

- `path` _str_ - Absolute path of the directory to create.
  

**Returns**:

- `FileEntry` - The created (or already-existing) directory entry.

<a id="wrenn.files.Files.remove"></a>

#### remove

```python
def remove(path: str) -> None
```

Remove a file or directory recursively.

**Arguments**:

- `path` _str_ - Absolute path to remove.
  

**Raises**:

- `WrennNotFoundError` - If the path does not exist.

<a id="wrenn.files.Files.upload_stream"></a>

#### upload\_stream

```python
def upload_stream(path: str, stream: Iterator[bytes]) -> None
```

Stream a large file into the capsule.

Prefer this over :meth:`write` when the file is too large to hold in
memory.

**Arguments**:

- `path` _str_ - Absolute destination path inside the capsule.
- `stream` _Iterator[bytes]_ - Iterable of byte chunks to upload.

<a id="wrenn.files.Files.download_stream"></a>

#### download\_stream

```python
def download_stream(path: str) -> Iterator[bytes]
```

Stream a large file out of the capsule.

Prefer this over :meth:`read_bytes` when the file is too large to hold
in memory.

**Arguments**:

- `path` _str_ - Absolute path to the file inside the capsule.
  

**Yields**:

- `bytes` - Successive byte chunks of the file.
  

**Raises**:

- `WrennNotFoundError` - If the path does not exist.

<a id="wrenn.files.AsyncFiles"></a>

## AsyncFiles Objects

```python
class AsyncFiles()
```

Async filesystem interface. Accessed via ``capsule.files``.

<a id="wrenn.files.AsyncFiles.read"></a>

#### read

```python
async def read(path: str) -> str
```

Read a file as a UTF-8 string.

**Arguments**:

- `path` _str_ - Absolute path to the file inside the capsule.
  

**Returns**:

- `str` - File contents decoded as UTF-8.
  

**Raises**:

- `WrennNotFoundError` - If the path does not exist.

<a id="wrenn.files.AsyncFiles.read_bytes"></a>

#### read\_bytes

```python
async def read_bytes(path: str) -> bytes
```

Read a file as raw bytes.

**Arguments**:

- `path` _str_ - Absolute path to the file inside the capsule.
  

**Returns**:

- `bytes` - Raw file contents.
  

**Raises**:

- `WrennNotFoundError` - If the path does not exist.

<a id="wrenn.files.AsyncFiles.write"></a>

#### write

```python
async def write(path: str, data: str | bytes) -> None
```

Write data to a file inside the capsule.

Creates parent directories if they do not exist.

**Arguments**:

- `path` _str_ - Absolute destination path inside the capsule.
- `data` _str | bytes_ - Content to write. Strings are UTF-8 encoded.

<a id="wrenn.files.AsyncFiles.list"></a>

#### list

```python
async def list(path: str, depth: int = 1) -> list[FileEntry]
```

List directory contents.

**Arguments**:

- `path` _str_ - Absolute path to the directory inside the capsule.
- `depth` _int_ - Recursion depth. ``1`` lists only immediate children.
  Defaults to ``1``.
  

**Returns**:

- `list[FileEntry]` - Entries in the directory.
  

**Raises**:

- `WrennNotFoundError` - If the path does not exist.

<a id="wrenn.files.AsyncFiles.exists"></a>

#### exists

```python
async def exists(path: str) -> bool
```

Check whether a path exists inside the capsule.

**Arguments**:

- `path` _str_ - Absolute path to check.
  

**Returns**:

- `bool` - ``True`` if the path exists.

<a id="wrenn.files.AsyncFiles.make_dir"></a>

#### make\_dir

```python
async def make_dir(path: str) -> FileEntry
```

Create a directory (with parents). Idempotent.

**Arguments**:

- `path` _str_ - Absolute path of the directory to create.
  

**Returns**:

- `FileEntry` - The created (or already-existing) directory entry.

<a id="wrenn.files.AsyncFiles.remove"></a>

#### remove

```python
async def remove(path: str) -> None
```

Remove a file or directory recursively.

**Arguments**:

- `path` _str_ - Absolute path to remove.
  

**Raises**:

- `WrennNotFoundError` - If the path does not exist.

<a id="wrenn.files.AsyncFiles.upload_stream"></a>

#### upload\_stream

```python
async def upload_stream(path: str, stream: AsyncIterator[bytes]) -> None
```

Stream a large file into the capsule.

Prefer this over :meth:`write` when the file is too large to hold in
memory.

**Arguments**:

- `path` _str_ - Absolute destination path inside the capsule.
- `stream` _AsyncIterator[bytes]_ - Async iterable of byte chunks to
  upload.

<a id="wrenn.files.AsyncFiles.download_stream"></a>

#### download\_stream

```python
async def download_stream(path: str) -> AsyncIterator[bytes]
```

Stream a large file out of the capsule.

Prefer this over :meth:`read_bytes` when the file is too large to hold
in memory.

**Arguments**:

- `path` _str_ - Absolute path to the file inside the capsule.
  

**Yields**:

- `bytes` - Successive byte chunks of the file.
  

**Raises**:

- `WrennNotFoundError` - If the path does not exist.

<a id="wrenn.code_interpreter.models"></a>

# wrenn.code\_interpreter.models

<a id="wrenn.code_interpreter.models.ExecutionError"></a>

## ExecutionError Objects

```python
@dataclass
class ExecutionError()
```

Error raised during code execution.

**Attributes**:

- `name` - Exception class name (e.g. ``"NameError"``).
- `value` - Exception message.
- `traceback` - Full traceback string.

<a id="wrenn.code_interpreter.models.Logs"></a>

## Logs Objects

```python
@dataclass
class Logs()
```

Captured stdout/stderr streams.

Each element in the list is one chunk of text as it arrived from
the kernel.

<a id="wrenn.code_interpreter.models.Result"></a>

## Result Objects

```python
@dataclass
class Result()
```

A single rich output from code execution.

Jupyter cells can produce multiple outputs — one ``execute_result``
(the expression value) and zero or more ``display_data`` messages
(from ``plt.show()``, ``display()``, etc.).  Each becomes a
``Result``.

Known MIME types are unpacked into named attributes; anything else
lands in :pyattr:`extra`.

<a id="wrenn.code_interpreter.models.Result.text"></a>

#### text

``text/plain`` representation.

<a id="wrenn.code_interpreter.models.Result.html"></a>

#### html

``text/html`` representation.

<a id="wrenn.code_interpreter.models.Result.markdown"></a>

#### markdown

``text/markdown`` representation.

<a id="wrenn.code_interpreter.models.Result.svg"></a>

#### svg

``image/svg+xml`` representation.

<a id="wrenn.code_interpreter.models.Result.png"></a>

#### png

``image/png`` — base64-encoded.

<a id="wrenn.code_interpreter.models.Result.jpeg"></a>

#### jpeg

``image/jpeg`` — base64-encoded.

<a id="wrenn.code_interpreter.models.Result.pdf"></a>

#### pdf

``application/pdf`` — base64-encoded.

<a id="wrenn.code_interpreter.models.Result.latex"></a>

#### latex

``text/latex`` representation.

<a id="wrenn.code_interpreter.models.Result.json"></a>

#### json

``application/json`` representation.

<a id="wrenn.code_interpreter.models.Result.javascript"></a>

#### javascript

``application/javascript`` representation.

<a id="wrenn.code_interpreter.models.Result.extra"></a>

#### extra

MIME types not covered by the named fields above.

<a id="wrenn.code_interpreter.models.Result.is_main_result"></a>

#### is\_main\_result

``True`` when this came from an ``execute_result`` message
(i.e. the value of the last expression in the cell).  ``False``
for ``display_data`` outputs.

<a id="wrenn.code_interpreter.models.Result.from_bundle"></a>

#### from\_bundle

```python
@classmethod
def from_bundle(cls,
                bundle: dict[str, str],
                *,
                is_main_result: bool = False) -> Result
```

Build a ``Result`` from a Jupyter MIME bundle dict.

<a id="wrenn.code_interpreter.models.Result.formats"></a>

#### formats

```python
def formats() -> list[str]
```

Return names of non-``None`` MIME-type fields.

<a id="wrenn.code_interpreter.models.Execution"></a>

## Execution Objects

```python
@dataclass
class Execution()
```

Complete result of a ``run_code`` call.

**Attributes**:

- `results` - All rich outputs produced by the cell — charts, tables,
  images, expression values, etc.
- `logs` - Captured stdout/stderr text.
- `error` - Populated when the cell raised an exception.
- `execution_count` - Jupyter execution counter (the ``[N]`` number).

<a id="wrenn.code_interpreter.models.Execution.text"></a>

#### text

```python
@property
def text() -> str | None
```

Convenience — ``text/plain`` of the main ``execute_result``,
or ``None`` if the cell had no expression value.

<a id="wrenn.code_interpreter.async_capsule"></a>

# wrenn.code\_interpreter.async\_capsule

<a id="wrenn.code_interpreter.async_capsule.AsyncCapsule"></a>

## AsyncCapsule Objects

```python
class AsyncCapsule(BaseAsyncCapsule)
```

Async code interpreter capsule with ``run_code`` support.

Uses ``code-runner-beta`` template by default::

from wrenn.code_interpreter import AsyncCapsule

capsule = await AsyncCapsule.create()
result = await capsule.run_code("print('hello')")

<a id="wrenn.code_interpreter.async_capsule.AsyncCapsule.create"></a>

#### create

```python
@classmethod
async def create(cls,
                 template: str | None = None,
                 vcpus: int | None = None,
                 memory_mb: int | None = None,
                 timeout: int | None = None,
                 *,
                 wait: bool = False,
                 api_key: str | None = None,
                 base_url: str | None = None) -> AsyncCapsule
```

Create a new async code interpreter capsule.

**Arguments**:

- `template` _str | None_ - Template to boot from. Defaults to
  ``"code-runner-beta"``.
- `vcpus` _int | None_ - Number of virtual CPUs.
- `memory_mb` _int | None_ - Memory in MiB.
- `timeout` _int | None_ - Inactivity TTL in seconds before auto-pause.
- `wait` _bool_ - Await until the capsule reaches ``running`` status.
- `api_key` _str | None_ - Wrenn API key. Falls back to
  ``WRENN_API_KEY`` env var.
- `base_url` _str | None_ - API base URL override.
  

**Returns**:

- `AsyncCapsule` - A new async code interpreter capsule instance.

<a id="wrenn.code_interpreter.async_capsule.AsyncCapsule.run_code"></a>

#### run\_code

```python
async def run_code(
        code: str,
        language: str = "python",
        timeout: float = 30,
        jupyter_timeout: float = 30,
        on_result: Callable[[Result], Any] | None = None,
        on_stdout: Callable[[str], Any] | None = None,
        on_stderr: Callable[[str], Any] | None = None,
        on_error: Callable[[ExecutionError], Any] | None = None) -> Execution
```

Execute code in a persistent Jupyter kernel (async).

**Arguments**:

- `code` - Code string to execute.
- `language` - Execution backend language. Currently only ``"python"``.
- `timeout` - Maximum seconds to wait for execution to complete.
- `jupyter_timeout` - Maximum seconds to wait for Jupyter to become
  available.
- `on_result` - Called for each rich output (charts, images, expression
  values).
- `on_stdout` - Called for each stdout chunk.
- `on_stderr` - Called for each stderr chunk.
- `on_error` - Called when the cell raises an exception.
  

**Returns**:

  An :class:`Execution` with ``.results``, ``.logs``, ``.error``,
  and a convenience ``.text`` property.

<a id="wrenn.code_interpreter"></a>

# wrenn.code\_interpreter

<a id="wrenn.code_interpreter.capsule"></a>

# wrenn.code\_interpreter.capsule

<a id="wrenn.code_interpreter.capsule.Capsule"></a>

## Capsule Objects

```python
class Capsule(BaseCapsule)
```

Code interpreter capsule with ``run_code`` support.

Uses ``code-runner-beta`` template by default::

from wrenn.code_interpreter import Capsule

capsule = Capsule()
result = capsule.run_code("print('hello')")
print(result.logs.stdout)  # ["hello\n"]

<a id="wrenn.code_interpreter.capsule.Capsule.__init__"></a>

#### \_\_init\_\_

```python
def __init__(template: str | None = None,
             vcpus: int | None = None,
             memory_mb: int | None = None,
             timeout: int | None = None,
             *,
             api_key: str | None = None,
             base_url: str | None = None,
             **kwargs) -> None
```

Create a code interpreter capsule.

**Arguments**:

- `template` _str | None_ - Template to boot from. Defaults to
  ``"code-runner-beta"``.
- `vcpus` _int | None_ - Number of virtual CPUs.
- `memory_mb` _int | None_ - Memory in MiB.
- `timeout` _int | None_ - Inactivity TTL in seconds before auto-pause.
- `api_key` _str | None_ - Wrenn API key. Falls back to
  ``WRENN_API_KEY`` env var.
- `base_url` _str | None_ - API base URL override.

<a id="wrenn.code_interpreter.capsule.Capsule.create"></a>

#### create

```python
@classmethod
def create(cls,
           template: str | None = None,
           vcpus: int | None = None,
           memory_mb: int | None = None,
           timeout: int | None = None,
           *,
           wait: bool = False,
           api_key: str | None = None,
           base_url: str | None = None) -> Capsule
```

Create a new code interpreter capsule.

**Arguments**:

- `template` _str | None_ - Template to boot from. Defaults to
  ``"code-runner-beta"``.
- `vcpus` _int | None_ - Number of virtual CPUs.
- `memory_mb` _int | None_ - Memory in MiB.
- `timeout` _int | None_ - Inactivity TTL in seconds before auto-pause.
- `wait` _bool_ - Block until the capsule reaches ``running`` status.
- `api_key` _str | None_ - Wrenn API key. Falls back to
  ``WRENN_API_KEY`` env var.
- `base_url` _str | None_ - API base URL override.
  

**Returns**:

- `Capsule` - A new code interpreter capsule instance.

<a id="wrenn.code_interpreter.capsule.Capsule.run_code"></a>

#### run\_code

```python
def run_code(
        code: str,
        language: str = "python",
        timeout: float = 30,
        jupyter_timeout: float = 30,
        on_result: Callable[[Result], Any] | None = None,
        on_stdout: Callable[[str], Any] | None = None,
        on_stderr: Callable[[str], Any] | None = None,
        on_error: Callable[[ExecutionError], Any] | None = None) -> Execution
```

Execute code in a persistent Jupyter kernel.

Variables, imports, and function definitions survive across calls.

**Arguments**:

- `code` - Code string to execute.
- `language` - Execution backend language. Currently only ``"python"``.
- `timeout` - Maximum seconds to wait for execution to complete.
- `jupyter_timeout` - Maximum seconds to wait for Jupyter to become
  available.
- `on_result` - Called for each rich output (charts, images, expression
  values).
- `on_stdout` - Called for each stdout chunk.
- `on_stderr` - Called for each stderr chunk.
- `on_error` - Called when the cell raises an exception.
  

**Returns**:

  An :class:`Execution` with ``.results``, ``.logs``, ``.error``,
  and a convenience ``.text`` property.

<a id="wrenn.exceptions"></a>

# wrenn.exceptions

<a id="wrenn.exceptions.WrennError"></a>

## WrennError Objects

```python
class WrennError(Exception)
```

Base exception for all Wrenn SDK errors.

All SDK exceptions inherit from this class, so you can catch
``WrennError`` to handle any API error generically.

**Attributes**:

- `code` _str_ - Machine-readable error code from the API
  (e.g. ``"not_found"``).
- `message` _str_ - Human-readable error description.
- `status_code` _int_ - HTTP status code of the response.

<a id="wrenn.exceptions.WrennError.__init__"></a>

#### \_\_init\_\_

```python
def __init__(code: str, message: str, status_code: int) -> None
```

Initialize a WrennError.

**Arguments**:

- `code` _str_ - Machine-readable error code.
- `message` _str_ - Human-readable error description.
- `status_code` _int_ - HTTP status code of the response.

<a id="wrenn.exceptions.WrennValidationError"></a>

## WrennValidationError Objects

```python
class WrennValidationError(WrennError)
```

400 — Invalid request parameters.

<a id="wrenn.exceptions.WrennAuthenticationError"></a>

## WrennAuthenticationError Objects

```python
class WrennAuthenticationError(WrennError)
```

401 — Invalid or missing authentication.

<a id="wrenn.exceptions.WrennForbiddenError"></a>

## WrennForbiddenError Objects

```python
class WrennForbiddenError(WrennError)
```

403 — Authenticated but not authorized.

<a id="wrenn.exceptions.WrennNotFoundError"></a>

## WrennNotFoundError Objects

```python
class WrennNotFoundError(WrennError)
```

404 — Resource not found.

<a id="wrenn.exceptions.WrennConflictError"></a>

## WrennConflictError Objects

```python
class WrennConflictError(WrennError)
```

409 — State conflict (e.g. invalid_state).

<a id="wrenn.exceptions.WrennHostHasCapsulesError"></a>

## WrennHostHasCapsulesError Objects

```python
class WrennHostHasCapsulesError(WrennConflictError)
```

409 — Host still has running capsules.

**Attributes**:

- `capsule_ids` _list[str]_ - IDs of the capsules still running on the host.

<a id="wrenn.exceptions.WrennHostHasCapsulesError.__init__"></a>

#### \_\_init\_\_

```python
def __init__(code: str, message: str, status_code: int,
             capsule_ids: list[str]) -> None
```

Initialize a WrennHostHasCapsulesError.

**Arguments**:

- `code` _str_ - Machine-readable error code.
- `message` _str_ - Human-readable error description.
- `status_code` _int_ - HTTP status code of the response.
- `capsule_ids` _list[str]_ - IDs of capsules still on the host.

<a id="wrenn.exceptions.WrennHostUnavailableError"></a>

## WrennHostUnavailableError Objects

```python
class WrennHostUnavailableError(WrennError)
```

503 — No suitable host available.

<a id="wrenn.exceptions.WrennAgentError"></a>

## WrennAgentError Objects

```python
class WrennAgentError(WrennError)
```

502 — Host agent returned an error.

<a id="wrenn.exceptions.WrennInternalError"></a>

## WrennInternalError Objects

```python
class WrennInternalError(WrennError)
```

500 — Unexpected server error.

<a id="wrenn.async_capsule"></a>

# wrenn.async\_capsule

<a id="wrenn.async_capsule.AsyncCapsule"></a>

## AsyncCapsule Objects

```python
class AsyncCapsule()
```

Async Wrenn capsule with e2b-compatible interface.

Create via classmethod::

capsule = await AsyncCapsule.create(template="minimal")

Use as async context manager::

async with await AsyncCapsule.create() as capsule:
await capsule.commands.run("echo hello")

<a id="wrenn.async_capsule.AsyncCapsule.capsule_id"></a>

#### capsule\_id

```python
@property
def capsule_id() -> str
```

The capsule's unique identifier.

**Returns**:

- `str` - Capsule ID assigned by the Wrenn API.

<a id="wrenn.async_capsule.AsyncCapsule.info"></a>

#### info

```python
@property
def info() -> CapsuleModel | None
```

Cached capsule metadata from the last API call.

**Returns**:

  CapsuleModel | None: The last-fetched capsule model, or ``None``
  if the capsule was connected without an initial fetch.

<a id="wrenn.async_capsule.AsyncCapsule.create"></a>

#### create

```python
@classmethod
async def create(cls,
                 template: str | None = None,
                 vcpus: int | None = None,
                 memory_mb: int | None = None,
                 timeout: int | None = None,
                 *,
                 wait: bool = False,
                 api_key: str | None = None,
                 base_url: str | None = None) -> AsyncCapsule
```

Create a new capsule.

**Arguments**:

- `template` _str | None_ - Template name to boot from.
- `vcpus` _int | None_ - Number of virtual CPUs.
- `memory_mb` _int | None_ - Memory in MiB.
- `timeout` _int | None_ - Inactivity TTL in seconds before auto-pause.
- `wait` _bool_ - Await until the capsule reaches ``running`` status.
- `api_key` _str | None_ - Wrenn API key. Falls back to
  ``WRENN_API_KEY`` env var.
- `base_url` _str | None_ - API base URL override.
  

**Returns**:

- `AsyncCapsule` - A new capsule instance.

<a id="wrenn.async_capsule.AsyncCapsule.connect"></a>

#### connect

```python
@classmethod
async def connect(cls,
                  capsule_id: str,
                  *,
                  api_key: str | None = None,
                  base_url: str | None = None) -> AsyncCapsule
```

Connect to an existing capsule, resuming it if paused.

**Arguments**:

- `capsule_id` _str_ - ID of the capsule to connect to.
- `api_key` _str | None_ - Wrenn API key. Falls back to
  ``WRENN_API_KEY`` env var.
- `base_url` _str | None_ - API base URL override.
  

**Returns**:

- `AsyncCapsule` - A capsule instance bound to the existing capsule.
  

**Raises**:

- `WrennNotFoundError` - If no capsule with the given ID exists.

<a id="wrenn.async_capsule.AsyncCapsule.ping"></a>

#### ping

```python
async def ping() -> None
```

Reset the capsule inactivity timer.

Call this to prevent the capsule from being auto-paused when the
inactivity TTL is set.

<a id="wrenn.async_capsule.AsyncCapsule.wait_ready"></a>

#### wait\_ready

```python
async def wait_ready(timeout: float = 30, interval: float = 0.5) -> None
```

Await until the capsule status is ``running``.

**Arguments**:

- `timeout` _float_ - Maximum seconds to wait. Defaults to ``30``.
- `interval` _float_ - Polling interval in seconds. Defaults to ``0.5``.
  

**Raises**:

- `TimeoutError` - If the capsule does not reach ``running`` state
  within ``timeout`` seconds.
- `RuntimeError` - If the capsule enters an error, stopped, or paused
  state while waiting.

<a id="wrenn.async_capsule.AsyncCapsule.is_running"></a>

#### is\_running

```python
async def is_running() -> bool
```

Check whether the capsule is currently running.

Makes a live API call to fetch current status.

**Returns**:

- `bool` - ``True`` if the capsule status is ``running``.

<a id="wrenn.async_capsule.AsyncCapsule.list"></a>

#### list

```python
@classmethod
async def list(cls,
               *,
               api_key: str | None = None,
               base_url: str | None = None) -> list[CapsuleModel]
```

List all capsules belonging to the team.

**Arguments**:

- `api_key` _str | None_ - Wrenn API key. Falls back to
  ``WRENN_API_KEY`` env var.
- `base_url` _str | None_ - API base URL override.
  

**Returns**:

- `list[CapsuleModel]` - All capsules for the authenticated team.

<a id="wrenn.async_capsule.AsyncCapsule.pty"></a>

#### pty

```python
@asynccontextmanager
async def pty(cmd: str = "/bin/bash",
              args: list[str] | None = None,
              cols: int = 80,
              rows: int = 24,
              envs: dict[str, str] | None = None,
              cwd: str | None = None) -> AsyncIterator[AsyncPtySession]
```

Open an async interactive PTY session backed by a WebSocket.

Use as an async context manager and async iterate over
:class:`PtyEvent` objects::

async with capsule.pty() as term:
await term.write(b"echo hello\n")
async for event in term:
if event.type == "output":
print(event.data.decode())

**Arguments**:

- `cmd` _str_ - Command to run inside the PTY. Defaults to
  ``"/bin/bash"``.
- `args` _list[str] | None_ - Additional arguments for ``cmd``.
- `cols` _int_ - Initial terminal column count. Defaults to ``80``.
- `rows` _int_ - Initial terminal row count. Defaults to ``24``.
- `envs` _dict[str, str] | None_ - Additional environment variables
  to inject into the process.
- `cwd` _str | None_ - Working directory for the process.
  

**Yields**:

- `AsyncPtySession` - An interactive async PTY session.

<a id="wrenn.async_capsule.AsyncCapsule.pty_connect"></a>

#### pty\_connect

```python
@asynccontextmanager
async def pty_connect(tag: str) -> AsyncIterator[AsyncPtySession]
```

Reconnect to an existing PTY session by tag.

**Arguments**:

- `tag` _str_ - Session tag returned in the ``started`` PTY event.
  

**Yields**:

- `AsyncPtySession` - The reconnected async PTY session.

<a id="wrenn.async_capsule.AsyncCapsule.get_url"></a>

#### get\_url

```python
def get_url(port: int) -> str
```

Get the proxy URL for a port exposed inside this capsule.

**Arguments**:

- `port` _int_ - Port number to proxy.
  

**Returns**:

- `str` - A ``wss://`` (or ``ws://``) URL that proxies to the given
  port inside the capsule.

<a id="wrenn.async_capsule.AsyncCapsule.create_snapshot"></a>

#### create\_snapshot

```python
async def create_snapshot(name: str | None = None,
                          overwrite: bool = False) -> Template
```

Create a snapshot template from this capsule's current state.

**Arguments**:

- `name` _str | None_ - Name for the snapshot template. Auto-generated
  if not provided.
- `overwrite` _bool_ - If ``True``, overwrite an existing template with
  the same name. Defaults to ``False``.
  

**Returns**:

- `Template` - The created snapshot template.

<a id="wrenn.pty"></a>

# wrenn.pty

<a id="wrenn.pty.PtySession"></a>

## PtySession Objects

```python
class PtySession()
```

Interactive PTY session backed by a WebSocket.

Use as a context manager and iterate over events::

with sb.pty(cmd="/bin/bash") as term:
term.write(b"ls -la\n")
for event in term:
if event.type == "output":
sys.stdout.buffer.write(event.data)
elif event.type == "exit":
break

<a id="wrenn.pty.PtySession.tag"></a>

#### tag

```python
@property
def tag() -> str | None
```

Session tag. Available after the ``started`` event.

<a id="wrenn.pty.PtySession.pid"></a>

#### pid

```python
@property
def pid() -> int | None
```

Process PID. Available after the ``started`` event.

<a id="wrenn.pty.PtySession.write"></a>

#### write

```python
def write(data: bytes) -> None
```

Send raw bytes to the PTY stdin.

**Arguments**:

- `data` - Raw bytes to send. Base64-encoded internally.

<a id="wrenn.pty.PtySession.resize"></a>

#### resize

```python
def resize(cols: int, rows: int) -> None
```

Resize the PTY terminal.

**Arguments**:

- `cols` - New column count. Must be > 0.
- `rows` - New row count. Must be > 0.
  

**Raises**:

- `ValueError` - If cols or rows is 0.

<a id="wrenn.pty.PtySession.kill"></a>

#### kill

```python
def kill() -> None
```

Send SIGKILL to the PTY process.

<a id="wrenn.pty.AsyncPtySession"></a>

## AsyncPtySession Objects

```python
class AsyncPtySession()
```

Async interactive PTY session backed by a WebSocket.

Use as an async context manager and async iterate over events::

async with sb.pty(cmd="/bin/bash") as term:
await term.write(b"ls -la\n")
async for event in term:
if event.type == "output":
sys.stdout.buffer.write(event.data)
elif event.type == "exit":
break

<a id="wrenn.pty.AsyncPtySession.tag"></a>

#### tag

```python
@property
def tag() -> str | None
```

Session tag. Available after the ``started`` event.

<a id="wrenn.pty.AsyncPtySession.pid"></a>

#### pid

```python
@property
def pid() -> int | None
```

Process PID. Available after the ``started`` event.

<a id="wrenn.pty.AsyncPtySession.write"></a>

#### write

```python
async def write(data: bytes) -> None
```

Send raw bytes to the PTY stdin.

**Arguments**:

- `data` - Raw bytes to send. Base64-encoded internally.

<a id="wrenn.pty.AsyncPtySession.resize"></a>

#### resize

```python
async def resize(cols: int, rows: int) -> None
```

Resize the PTY terminal.

**Arguments**:

- `cols` - New column count. Must be > 0.
- `rows` - New row count. Must be > 0.
  

**Raises**:

- `ValueError` - If cols or rows is 0.

<a id="wrenn.pty.AsyncPtySession.kill"></a>

#### kill

```python
async def kill() -> None
```

Send SIGKILL to the PTY process.

<a id="wrenn.models._generated"></a>

# wrenn.models.\_generated

<a id="wrenn.models._generated.Peaks"></a>

## Peaks Objects

```python
class Peaks(BaseModel)
```

Maximum values over the last 30 days.

<a id="wrenn.models._generated.Series"></a>

## Series Objects

```python
class Series(BaseModel)
```

Parallel arrays for chart rendering.

<a id="wrenn.models._generated.Encoding"></a>

## Encoding Objects

```python
class Encoding(StrEnum)
```

Output encoding. "base64" when stdout/stderr contain binary data.

<a id="wrenn.models._generated.Type2"></a>

## Type2 Objects

```python
class Type2(StrEnum)
```

Host type. Regular hosts are shared; BYOC hosts belong to a team.

<a id="wrenn.models"></a>

# wrenn.models

<a id="wrenn.capsule"></a>

# wrenn.capsule

<a id="wrenn.capsule.Capsule"></a>

## Capsule Objects

```python
class Capsule()
```

A Wrenn capsule (sandbox) with e2b-compatible interface.

Create directly::

capsule = Capsule(api_key="wrn_...")
capsule = Capsule(template="minimal")  # reads WRENN_API_KEY env

Or via classmethod::

capsule = Capsule.create(template="minimal")

Use as context manager for automatic cleanup::

with Capsule() as capsule:
capsule.commands.run("echo hello")

<a id="wrenn.capsule.Capsule.__init__"></a>

#### \_\_init\_\_

```python
def __init__(template: str | None = None,
             vcpus: int | None = None,
             memory_mb: int | None = None,
             timeout: int | None = None,
             *,
             wait: bool = False,
             api_key: str | None = None,
             base_url: str | None = None,
             _capsule_id: str | None = None,
             _client: WrennClient | None = None,
             _info: CapsuleModel | None = None) -> None
```

Create and start a new capsule.

**Arguments**:

- `template` _str | None_ - Template name to boot from. Defaults to
  the server-side default (``"minimal"``).
- `vcpus` _int | None_ - Number of virtual CPUs. Defaults to the
  server-side default.
- `memory_mb` _int | None_ - Memory in MiB. Defaults to the
  server-side default.
- `timeout` _int | None_ - Inactivity TTL in seconds before the capsule
  is auto-paused. ``0`` disables auto-pause.
- `wait` _bool_ - If ``True``, block until the capsule status is
  ``running`` before returning.
- `api_key` _str | None_ - Wrenn API key (``wrn_...``). Falls back to
  the ``WRENN_API_KEY`` environment variable.
- `base_url` _str | None_ - Wrenn API base URL. Falls back to
  ``WRENN_BASE_URL`` or the default production endpoint.

<a id="wrenn.capsule.Capsule.capsule_id"></a>

#### capsule\_id

```python
@property
def capsule_id() -> str
```

The capsule's unique identifier.

**Returns**:

- `str` - Capsule ID assigned by the Wrenn API.

<a id="wrenn.capsule.Capsule.info"></a>

#### info

```python
@property
def info() -> CapsuleModel | None
```

Cached capsule metadata from the last API call.

**Returns**:

  CapsuleModel | None: The last-fetched capsule model, or ``None``
  if the capsule was connected without an initial fetch.

<a id="wrenn.capsule.Capsule.create"></a>

#### create

```python
@classmethod
def create(cls,
           template: str | None = None,
           vcpus: int | None = None,
           memory_mb: int | None = None,
           timeout: int | None = None,
           *,
           wait: bool = False,
           api_key: str | None = None,
           base_url: str | None = None) -> Capsule
```

Create a new capsule.

Equivalent to calling ``Capsule(...)`` directly.

**Arguments**:

- `template` _str | None_ - Template name to boot from.
- `vcpus` _int | None_ - Number of virtual CPUs.
- `memory_mb` _int | None_ - Memory in MiB.
- `timeout` _int | None_ - Inactivity TTL in seconds before auto-pause.
- `wait` _bool_ - Block until the capsule reaches ``running`` status.
- `api_key` _str | None_ - Wrenn API key. Falls back to
  ``WRENN_API_KEY`` env var.
- `base_url` _str | None_ - API base URL override.
  

**Returns**:

- `Capsule` - A new capsule instance.

<a id="wrenn.capsule.Capsule.connect"></a>

#### connect

```python
@classmethod
def connect(cls,
            capsule_id: str,
            *,
            api_key: str | None = None,
            base_url: str | None = None) -> Capsule
```

Connect to an existing capsule, resuming it if paused.

**Arguments**:

- `capsule_id` _str_ - ID of the capsule to connect to.
- `api_key` _str | None_ - Wrenn API key. Falls back to
  ``WRENN_API_KEY`` env var.
- `base_url` _str | None_ - API base URL override.
  

**Returns**:

- `Capsule` - A capsule instance bound to the existing capsule.
  

**Raises**:

- `WrennNotFoundError` - If no capsule with the given ID exists.

<a id="wrenn.capsule.Capsule.ping"></a>

#### ping

```python
def ping() -> None
```

Reset the capsule inactivity timer.

Call this to prevent the capsule from being auto-paused when the
inactivity TTL is set.

<a id="wrenn.capsule.Capsule.wait_ready"></a>

#### wait\_ready

```python
def wait_ready(timeout: float = 30, interval: float = 0.5) -> None
```

Block until the capsule status is ``running``.

**Arguments**:

- `timeout` _float_ - Maximum seconds to wait. Defaults to ``30``.
- `interval` _float_ - Polling interval in seconds. Defaults to ``0.5``.
  

**Raises**:

- `TimeoutError` - If the capsule does not reach ``running`` state
  within ``timeout`` seconds.
- `RuntimeError` - If the capsule enters an error, stopped, or paused
  state while waiting.

<a id="wrenn.capsule.Capsule.is_running"></a>

#### is\_running

```python
def is_running() -> bool
```

Check whether the capsule is currently running.

Makes a live API call to fetch current status.

**Returns**:

- `bool` - ``True`` if the capsule status is ``running``.

<a id="wrenn.capsule.Capsule.list"></a>

#### list

```python
@classmethod
def list(cls,
         *,
         api_key: str | None = None,
         base_url: str | None = None) -> list[CapsuleModel]
```

List all capsules belonging to the team.

**Arguments**:

- `api_key` _str | None_ - Wrenn API key. Falls back to
  ``WRENN_API_KEY`` env var.
- `base_url` _str | None_ - API base URL override.
  

**Returns**:

- `list[CapsuleModel]` - All capsules for the authenticated team.

<a id="wrenn.capsule.Capsule.pty"></a>

#### pty

```python
@contextmanager
def pty(cmd: str = "/bin/bash",
        args: list[str] | None = None,
        cols: int = 80,
        rows: int = 24,
        envs: dict[str, str] | None = None,
        cwd: str | None = None) -> Iterator[PtySession]
```

Open an interactive PTY session backed by a WebSocket.

Use as a context manager and iterate over :class:`PtyEvent` objects::

with capsule.pty() as term:
term.write(b"echo hello\n")
for event in term:
if event.type == "output":
print(event.data.decode())

**Arguments**:

- `cmd` _str_ - Command to run inside the PTY. Defaults to
  ``"/bin/bash"``.
- `args` _list[str] | None_ - Additional arguments for ``cmd``.
- `cols` _int_ - Initial terminal column count. Defaults to ``80``.
- `rows` _int_ - Initial terminal row count. Defaults to ``24``.
- `envs` _dict[str, str] | None_ - Additional environment variables to
  inject into the process.
- `cwd` _str | None_ - Working directory for the process.
  

**Yields**:

- `PtySession` - An interactive PTY session.

<a id="wrenn.capsule.Capsule.pty_connect"></a>

#### pty\_connect

```python
@contextmanager
def pty_connect(tag: str) -> Iterator[PtySession]
```

Reconnect to an existing PTY session by tag.

**Arguments**:

- `tag` _str_ - Session tag returned in the ``started`` PTY event.
  

**Yields**:

- `PtySession` - The reconnected PTY session.

<a id="wrenn.capsule.Capsule.get_url"></a>

#### get\_url

```python
def get_url(port: int) -> str
```

Get the proxy URL for a port exposed inside this capsule.

**Arguments**:

- `port` _int_ - Port number to proxy.
  

**Returns**:

- `str` - A ``wss://`` (or ``ws://``) URL that proxies to the given
  port inside the capsule.

<a id="wrenn.capsule.Capsule.create_snapshot"></a>

#### create\_snapshot

```python
def create_snapshot(name: str | None = None,
                    overwrite: bool = False) -> Template
```

Create a snapshot template from this capsule's current state.

**Arguments**:

- `name` _str | None_ - Name for the snapshot template. Auto-generated
  if not provided.
- `overwrite` _bool_ - If ``True``, overwrite an existing template with
  the same name. Defaults to ``False``.
  

**Returns**:

- `Template` - The created snapshot template.

<a id="wrenn._config"></a>

# wrenn.\_config

<a id="wrenn._config.ConnectionConfig"></a>

## ConnectionConfig Objects

```python
@dataclass(frozen=True)
class ConnectionConfig()
```

Resolved credentials and base URL for Wrenn API calls.

<a id="wrenn._git._auth"></a>

# wrenn.\_git.\_auth

<a id="wrenn._git._auth.embed_credentials"></a>

#### embed\_credentials

```python
def embed_credentials(url: str, username: str, password: str) -> str
```

Embed HTTP(S) credentials into a git URL.

**Arguments**:

- `url` - Git repository URL.
- `username` - Username for authentication.
- `password` - Password or personal access token.
  

**Returns**:

  URL with ``username:password@`` embedded in the netloc.
  

**Raises**:

- `ValueError` - If the URL scheme is not ``http`` or ``https``.

<a id="wrenn._git._auth.strip_credentials"></a>

#### strip\_credentials

```python
def strip_credentials(url: str) -> str
```

Remove embedded credentials from a git URL.

**Arguments**:

- `url` - Git repository URL, possibly with credentials.
  

**Returns**:

  URL with credentials removed. Non-HTTP(S) URLs are returned
  unchanged.

<a id="wrenn._git._auth.is_auth_error"></a>

#### is\_auth\_error

```python
def is_auth_error(stderr: str) -> bool
```

Check whether git stderr indicates an authentication failure.

**Arguments**:

- `stderr` - Combined stderr output from a git command.
  

**Returns**:

  ``True`` if any known auth-failure pattern is found.

<a id="wrenn._git._auth.build_credential_approve_cmd"></a>

#### build\_credential\_approve\_cmd

```python
def build_credential_approve_cmd(username: str,
                                 password: str,
                                 host: str = "github.com",
                                 protocol: str = "https") -> str
```

Build a shell command that pipes credentials into ``git credential approve``.

**Arguments**:

- `username` - Git username.
- `password` - Password or personal access token.
- `host` - Target host. Defaults to ``"github.com"``.
- `protocol` - Protocol. Defaults to ``"https"``.
  

**Returns**:

  A shell command string safe to pass to ``commands.run()``.

<a id="wrenn._git._cmd"></a>

# wrenn.\_git.\_cmd

Pure functions that build git argument lists and parse git output.

No I/O, no network, no imports from ``wrenn``. Every ``build_*`` function
returns a ``list[str]`` suitable for ``shlex.join()``.  Every ``parse_*``
function takes raw stdout and returns a typed structure.

<a id="wrenn._git._cmd.FileStatus"></a>

## FileStatus Objects

```python
@dataclass
class FileStatus()
```

A single entry from ``git status --porcelain=v1``.

**Attributes**:

- `path` _str_ - File path relative to the repository root.
- `index_status` _str_ - Index (staged) status character.
- `work_tree_status` _str_ - Working-tree status character.
- `renamed_from` _str | None_ - Original path when status is a rename.

<a id="wrenn._git._cmd.FileStatus.staged"></a>

#### staged

```python
@property
def staged() -> bool
```

Whether the change is staged in the index.

<a id="wrenn._git._cmd.FileStatus.status"></a>

#### status

```python
@property
def status() -> str
```

Normalized human-readable status label.

<a id="wrenn._git._cmd.GitStatus"></a>

## GitStatus Objects

```python
@dataclass
class GitStatus()
```

Parsed output of ``git status --porcelain=v1 --branch``.

**Attributes**:

- `branch` _str | None_ - Current branch name, or ``None`` if detached.
- `upstream` _str | None_ - Upstream tracking branch.
- `ahead` _int_ - Commits ahead of upstream.
- `behind` _int_ - Commits behind upstream.
- `detached` _bool_ - Whether HEAD is detached.
- `files` _list[FileStatus]_ - Per-file status entries.

<a id="wrenn._git._cmd.GitStatus.is_clean"></a>

#### is\_clean

```python
@property
def is_clean() -> bool
```

``True`` when there are no changed or untracked files.

<a id="wrenn._git._cmd.GitStatus.has_staged"></a>

#### has\_staged

```python
@property
def has_staged() -> bool
```

``True`` when at least one file has staged changes.

<a id="wrenn._git._cmd.GitStatus.has_untracked"></a>

#### has\_untracked

```python
@property
def has_untracked() -> bool
```

``True`` when at least one file is untracked.

<a id="wrenn._git._cmd.GitStatus.has_conflicts"></a>

#### has\_conflicts

```python
@property
def has_conflicts() -> bool
```

``True`` when at least one file has merge conflicts.

<a id="wrenn._git._cmd.GitBranch"></a>

## GitBranch Objects

```python
@dataclass
class GitBranch()
```

A single branch entry.

**Attributes**:

- `name` _str_ - Branch name (short ref).
- `is_current` _bool_ - Whether this is the checked-out branch.

<a id="wrenn._git._cmd.build_clone"></a>

#### build\_clone

```python
def build_clone(url: str,
                dest: str | None = None,
                *,
                branch: str | None = None,
                depth: int | None = None) -> list[str]
```

Build ``git clone`` arguments.

<a id="wrenn._git._cmd.build_init"></a>

#### build\_init

```python
def build_init(path: str = ".",
               *,
               bare: bool = False,
               initial_branch: str | None = None) -> list[str]
```

Build ``git init`` arguments.

<a id="wrenn._git._cmd.build_add"></a>

#### build\_add

```python
def build_add(paths: list[str] | None = None,
              *,
              all: bool = False) -> list[str]
```

Build ``git add`` arguments.

<a id="wrenn._git._cmd.build_commit"></a>

#### build\_commit

```python
def build_commit(message: str,
                 *,
                 allow_empty: bool = False,
                 author_name: str | None = None,
                 author_email: str | None = None) -> list[str]
```

Build ``git commit`` arguments.

<a id="wrenn._git._cmd.build_push"></a>

#### build\_push

```python
def build_push(remote: str = "origin",
               branch: str | None = None,
               *,
               force: bool = False,
               set_upstream: bool = False) -> list[str]
```

Build ``git push`` arguments.

<a id="wrenn._git._cmd.build_pull"></a>

#### build\_pull

```python
def build_pull(remote: str = "origin",
               branch: str | None = None,
               *,
               rebase: bool = False,
               ff_only: bool = False) -> list[str]
```

Build ``git pull`` arguments.

<a id="wrenn._git._cmd.build_status"></a>

#### build\_status

```python
def build_status() -> list[str]
```

Build ``git status`` arguments for porcelain parsing.

<a id="wrenn._git._cmd.build_branches"></a>

#### build\_branches

```python
def build_branches() -> list[str]
```

Build ``git branch`` arguments for structured parsing.

<a id="wrenn._git._cmd.build_create_branch"></a>

#### build\_create\_branch

```python
def build_create_branch(name: str,
                        *,
                        start_point: str | None = None) -> list[str]
```

Build ``git checkout -b`` arguments.

<a id="wrenn._git._cmd.build_checkout"></a>

#### build\_checkout

```python
def build_checkout(name: str) -> list[str]
```

Build ``git checkout`` arguments.

<a id="wrenn._git._cmd.build_delete_branch"></a>

#### build\_delete\_branch

```python
def build_delete_branch(name: str, *, force: bool = False) -> list[str]
```

Build ``git branch -d/-D`` arguments.

<a id="wrenn._git._cmd.build_remote_add"></a>

#### build\_remote\_add

```python
def build_remote_add(name: str, url: str, *, fetch: bool = False) -> list[str]
```

Build ``git remote add`` arguments.

<a id="wrenn._git._cmd.build_remote_get_url"></a>

#### build\_remote\_get\_url

```python
def build_remote_get_url(name: str = "origin") -> list[str]
```

Build ``git remote get-url`` arguments.

<a id="wrenn._git._cmd.build_remote_set_url"></a>

#### build\_remote\_set\_url

```python
def build_remote_set_url(name: str, url: str) -> list[str]
```

Build ``git remote set-url`` arguments.

<a id="wrenn._git._cmd.build_reset"></a>

#### build\_reset

```python
def build_reset(*,
                mode: str | None = None,
                ref: str | None = None,
                paths: list[str] | None = None) -> list[str]
```

Build ``git reset`` arguments.

**Arguments**:

- `mode` - Reset mode (``soft``, ``mixed``, ``hard``, ``merge``, ``keep``).
- `ref` - Commit, branch, or ref to reset to.
- `paths` - Paths to reset (mutually exclusive with ``mode``).

<a id="wrenn._git._cmd.build_restore"></a>

#### build\_restore

```python
def build_restore(paths: list[str],
                  *,
                  staged: bool = False,
                  worktree: bool = False,
                  source: str | None = None) -> list[str]
```

Build ``git restore`` arguments.

**Arguments**:

- `paths` - Paths to restore.
- `staged` - Restore the index (unstage).
- `worktree` - Restore working-tree files.
- `source` - Commit or ref to restore from.

<a id="wrenn._git._cmd.build_config_set"></a>

#### build\_config\_set

```python
def build_config_set(key: str,
                     value: str,
                     *,
                     scope: str = "local",
                     repo_path: str | None = None) -> list[str]
```

Build ``git config`` set arguments.

<a id="wrenn._git._cmd.build_config_get"></a>

#### build\_config\_get

```python
def build_config_get(key: str,
                     *,
                     scope: str = "local",
                     repo_path: str | None = None) -> list[str]
```

Build ``git config --get`` arguments.

<a id="wrenn._git._cmd.build_has_upstream"></a>

#### build\_has\_upstream

```python
def build_has_upstream() -> list[str]
```

Build arguments to check if current branch has upstream tracking.

<a id="wrenn._git._cmd.parse_status"></a>

#### parse\_status

```python
def parse_status(stdout: str) -> GitStatus
```

Parse ``git status --porcelain=v1 --branch`` output.

**Arguments**:

- `stdout` - Raw stdout from the git status command.
  

**Returns**:

  Parsed :class:`GitStatus`.

<a id="wrenn._git._cmd.parse_branches"></a>

#### parse\_branches

```python
def parse_branches(stdout: str) -> list[GitBranch]
```

Parse ``git branch --format=%(refname:short)\t%(HEAD)`` output.

**Arguments**:

- `stdout` - Raw stdout from the git branch command.
  

**Returns**:

  List of :class:`GitBranch`.

<a id="wrenn._git.exceptions"></a>

# wrenn.\_git.exceptions

<a id="wrenn._git.exceptions.GitError"></a>

## GitError Objects

```python
class GitError(Exception)
```

Base exception for all git operations inside a capsule.

Not a subclass of :class:`WrennError` because git errors originate
from a process exit code, not an HTTP response.

**Attributes**:

- `message` _str_ - Human-readable error description.
- `stderr` _str_ - Raw stderr output from the git process.
- `exit_code` _int_ - Process exit code.

<a id="wrenn._git.exceptions.GitCommandError"></a>

## GitCommandError Objects

```python
class GitCommandError(GitError)
```

A git command exited with a non-zero exit code.

<a id="wrenn._git.exceptions.GitAuthError"></a>

## GitAuthError Objects

```python
class GitAuthError(GitError)
```

Authentication failed when communicating with a remote.

<a id="wrenn._git"></a>

# wrenn.\_git

Git operations inside a Wrenn capsule.

Provides :class:`Git` (sync) and :class:`AsyncGit` (async) interfaces
accessed via ``capsule.git``.  All operations execute the real ``git``
binary inside the capsule through :class:`~wrenn.commands.Commands`.

<a id="wrenn._git.Git"></a>

## Git Objects

```python
class Git()
```

Sync git interface. Accessed via ``capsule.git``.

Executes the real ``git`` binary inside the capsule through
:meth:`Commands.run`. Methods raise :class:`GitCommandError` (or
:class:`GitAuthError`) on non-zero exit codes.

<a id="wrenn._git.Git.clone"></a>

#### clone

```python
def clone(url: str,
          dest: str | None = None,
          *,
          branch: str | None = None,
          depth: int | None = None,
          username: str | None = None,
          password: str | None = None,
          dangerously_store_credentials: bool = False,
          cwd: str | None = None,
          envs: dict[str, str] | None = None,
          timeout: int | None = 300) -> CommandResult
```

Clone a remote repository into the capsule.

**Arguments**:

- `url` - Remote repository URL.
- `dest` - Destination path. Defaults to the repository name
  derived from the URL.
- `branch` - Branch or tag to check out.
- `depth` - Create a shallow clone with this many commits.
- `username` - Username for HTTP(S) authentication.
- `password` - Password or token for HTTP(S) authentication.
- `dangerously_store_credentials` - If ``True``, leave credentials
  embedded in the remote URL after cloning.
- `cwd` - Working directory for the command.
- `envs` - Extra environment variables.
- `timeout` - Command timeout in seconds. Defaults to ``300``.
  

**Returns**:

  Command result with stdout, stderr, exit_code, and duration.
  

**Raises**:

- `GitAuthError` - If the remote rejected authentication.
- `GitCommandError` - If clone failed for another reason.
- `ValueError` - If *password* is provided without *username*.

<a id="wrenn._git.Git.init"></a>

#### init

```python
def init(path: str = ".",
         *,
         bare: bool = False,
         initial_branch: str | None = None,
         cwd: str | None = None,
         envs: dict[str, str] | None = None,
         timeout: int | None = 30) -> CommandResult
```

Initialize a new git repository.

**Arguments**:

- `path` - Destination path for the repository.
- `bare` - Create a bare repository.
- `initial_branch` - Name for the initial branch (e.g. ``"main"``).
- `cwd` - Working directory for the command.
- `envs` - Extra environment variables.
- `timeout` - Command timeout in seconds.
  

**Returns**:

  Command result.
  

**Raises**:

- `GitCommandError` - If init failed.

<a id="wrenn._git.Git.add"></a>

#### add

```python
def add(paths: list[str] | None = None,
        *,
        all: bool = False,
        cwd: str | None = None,
        envs: dict[str, str] | None = None,
        timeout: int | None = 30) -> CommandResult
```

Stage files for commit.

**Arguments**:

- `paths` - Specific files to stage. If ``None``, stages the
  current directory (or all with ``all=True``).
- `all` - Stage all changes including untracked files.
- `cwd` - Working directory (repository root).
- `envs` - Extra environment variables.
- `timeout` - Command timeout in seconds.
  

**Returns**:

  Command result.
  

**Raises**:

- `GitCommandError` - If add failed.

<a id="wrenn._git.Git.commit"></a>

#### commit

```python
def commit(message: str,
           *,
           allow_empty: bool = False,
           author_name: str | None = None,
           author_email: str | None = None,
           cwd: str | None = None,
           envs: dict[str, str] | None = None,
           timeout: int | None = 30) -> CommandResult
```

Create a commit.

**Arguments**:

- `message` - Commit message.
- `allow_empty` - Allow creating a commit with no changes.
- `author_name` - Override the commit author name.
- `author_email` - Override the commit author email.
- `cwd` - Working directory (repository root).
- `envs` - Extra environment variables.
- `timeout` - Command timeout in seconds.
  

**Returns**:

  Command result.
  

**Raises**:

- `GitCommandError` - If commit failed.

<a id="wrenn._git.Git.push"></a>

#### push

```python
def push(remote: str = "origin",
         branch: str | None = None,
         *,
         force: bool = False,
         set_upstream: bool = False,
         username: str | None = None,
         password: str | None = None,
         cwd: str | None = None,
         envs: dict[str, str] | None = None,
         timeout: int | None = 60) -> CommandResult
```

Push commits to a remote.

**Arguments**:

- `remote` - Remote name. Defaults to ``"origin"``.
- `branch` - Branch to push. Defaults to the current branch.
- `force` - Force-push.
- `set_upstream` - Set upstream tracking reference.
- `username` - Username for HTTP(S) authentication.
- `password` - Password or token for HTTP(S) authentication.
- `cwd` - Working directory (repository root).
- `envs` - Extra environment variables.
- `timeout` - Command timeout in seconds.
  

**Returns**:

  Command result.
  

**Raises**:

- `GitAuthError` - If authentication failed.
- `GitCommandError` - If push failed.

<a id="wrenn._git.Git.pull"></a>

#### pull

```python
def pull(remote: str = "origin",
         branch: str | None = None,
         *,
         rebase: bool = False,
         ff_only: bool = False,
         username: str | None = None,
         password: str | None = None,
         cwd: str | None = None,
         envs: dict[str, str] | None = None,
         timeout: int | None = 60) -> CommandResult
```

Pull changes from a remote.

**Arguments**:

- `remote` - Remote name. Defaults to ``"origin"``.
- `branch` - Branch to pull.
- `rebase` - Rebase instead of merge.
- `ff_only` - Only allow fast-forward merges.
- `username` - Username for HTTP(S) authentication.
- `password` - Password or token for HTTP(S) authentication.
- `cwd` - Working directory (repository root).
- `envs` - Extra environment variables.
- `timeout` - Command timeout in seconds.
  

**Returns**:

  Command result.
  

**Raises**:

- `GitAuthError` - If authentication failed.
- `GitCommandError` - If pull failed.

<a id="wrenn._git.Git.status"></a>

#### status

```python
def status(*,
           cwd: str | None = None,
           envs: dict[str, str] | None = None,
           timeout: int | None = 30) -> GitStatus
```

Get repository status.

**Arguments**:

- `cwd` - Working directory (repository root).
- `envs` - Extra environment variables.
- `timeout` - Command timeout in seconds.
  

**Returns**:

  Parsed :class:`GitStatus` with branch info and file changes.
  

**Raises**:

- `GitCommandError` - If the command failed.

<a id="wrenn._git.Git.branches"></a>

#### branches

```python
def branches(*,
             cwd: str | None = None,
             envs: dict[str, str] | None = None,
             timeout: int | None = 30) -> list[GitBranch]
```

List local branches.

**Arguments**:

- `cwd` - Working directory (repository root).
- `envs` - Extra environment variables.
- `timeout` - Command timeout in seconds.
  

**Returns**:

  List of :class:`GitBranch`.
  

**Raises**:

- `GitCommandError` - If the command failed.

<a id="wrenn._git.Git.create_branch"></a>

#### create\_branch

```python
def create_branch(name: str,
                  *,
                  start_point: str | None = None,
                  cwd: str | None = None,
                  envs: dict[str, str] | None = None,
                  timeout: int | None = 30) -> CommandResult
```

Create and check out a new branch.

**Arguments**:

- `name` - Branch name.
- `start_point` - Commit or ref to branch from.
- `cwd` - Working directory (repository root).
- `envs` - Extra environment variables.
- `timeout` - Command timeout in seconds.
  

**Returns**:

  Command result.
  

**Raises**:

- `GitCommandError` - If the command failed.

<a id="wrenn._git.Git.checkout_branch"></a>

#### checkout\_branch

```python
def checkout_branch(name: str,
                    *,
                    cwd: str | None = None,
                    envs: dict[str, str] | None = None,
                    timeout: int | None = 30) -> CommandResult
```

Check out an existing branch.

**Arguments**:

- `name` - Branch name.
- `cwd` - Working directory (repository root).
- `envs` - Extra environment variables.
- `timeout` - Command timeout in seconds.
  

**Returns**:

  Command result.
  

**Raises**:

- `GitCommandError` - If the command failed.

<a id="wrenn._git.Git.delete_branch"></a>

#### delete\_branch

```python
def delete_branch(name: str,
                  *,
                  force: bool = False,
                  cwd: str | None = None,
                  envs: dict[str, str] | None = None,
                  timeout: int | None = 30) -> CommandResult
```

Delete a branch.

**Arguments**:

- `name` - Branch name.
- `force` - Force-delete with ``-D``.
- `cwd` - Working directory (repository root).
- `envs` - Extra environment variables.
- `timeout` - Command timeout in seconds.
  

**Returns**:

  Command result.
  

**Raises**:

- `GitCommandError` - If the command failed.

<a id="wrenn._git.Git.remote_add"></a>

#### remote\_add

```python
def remote_add(name: str,
               url: str,
               *,
               fetch: bool = False,
               cwd: str | None = None,
               envs: dict[str, str] | None = None,
               timeout: int | None = 30) -> CommandResult
```

Add a remote.

**Arguments**:

- `name` - Remote name (e.g. ``"origin"``).
- `url` - Remote URL.
- `fetch` - Fetch after adding.
- `cwd` - Working directory (repository root).
- `envs` - Extra environment variables.
- `timeout` - Command timeout in seconds.
  

**Returns**:

  Command result.
  

**Raises**:

- `GitCommandError` - If the command failed.

<a id="wrenn._git.Git.remote_get"></a>

#### remote\_get

```python
def remote_get(name: str = "origin",
               *,
               cwd: str | None = None,
               envs: dict[str, str] | None = None,
               timeout: int | None = 30) -> str | None
```

Get the URL of a remote.

Returns ``None`` if the remote does not exist rather than raising.

**Arguments**:

- `name` - Remote name. Defaults to ``"origin"``.
- `cwd` - Working directory (repository root).
- `envs` - Extra environment variables.
- `timeout` - Command timeout in seconds.
  

**Returns**:

  Remote URL or ``None``.

<a id="wrenn._git.Git.reset"></a>

#### reset

```python
def reset(*,
          mode: str | None = None,
          ref: str | None = None,
          paths: list[str] | None = None,
          cwd: str | None = None,
          envs: dict[str, str] | None = None,
          timeout: int | None = 30) -> CommandResult
```

Reset the current HEAD.

**Arguments**:

- `mode` - Reset mode (``soft``, ``mixed``, ``hard``, ``merge``,
  ``keep``).
- `ref` - Commit, branch, or ref to reset to.
- `paths` - Paths to reset.
- `cwd` - Working directory (repository root).
- `envs` - Extra environment variables.
- `timeout` - Command timeout in seconds.
  

**Returns**:

  Command result.
  

**Raises**:

- `GitCommandError` - If the command failed.

<a id="wrenn._git.Git.restore"></a>

#### restore

```python
def restore(paths: list[str],
            *,
            staged: bool = False,
            worktree: bool = False,
            source: str | None = None,
            cwd: str | None = None,
            envs: dict[str, str] | None = None,
            timeout: int | None = 30) -> CommandResult
```

Restore working-tree files or unstage changes.

**Arguments**:

- `paths` - Paths to restore.
- `staged` - Restore the index (unstage).
- `worktree` - Restore working-tree files.
- `source` - Commit or ref to restore from.
- `cwd` - Working directory (repository root).
- `envs` - Extra environment variables.
- `timeout` - Command timeout in seconds.
  

**Returns**:

  Command result.
  

**Raises**:

- `GitCommandError` - If the command failed.

<a id="wrenn._git.Git.set_config"></a>

#### set\_config

```python
def set_config(key: str,
               value: str,
               *,
               scope: str = "local",
               cwd: str | None = None,
               envs: dict[str, str] | None = None,
               timeout: int | None = 30) -> CommandResult
```

Set a git config value.

**Arguments**:

- `key` - Config key (e.g. ``"user.name"``).
- `value` - Config value.
- `scope` - Config scope: ``"local"``, ``"global"``, or
  ``"system"``.
- `cwd` - Working directory (repository root). Required when
  scope is ``"local"``.
- `envs` - Extra environment variables.
- `timeout` - Command timeout in seconds.
  

**Returns**:

  Command result.
  

**Raises**:

- `GitCommandError` - If the command failed.

<a id="wrenn._git.Git.get_config"></a>

#### get\_config

```python
def get_config(key: str,
               *,
               scope: str = "local",
               cwd: str | None = None,
               envs: dict[str, str] | None = None,
               timeout: int | None = 30) -> str | None
```

Get a git config value.

Returns ``None`` if the key is not set rather than raising.

**Arguments**:

- `key` - Config key (e.g. ``"user.name"``).
- `scope` - Config scope: ``"local"``, ``"global"``, or
  ``"system"``.
- `cwd` - Working directory (repository root). Required when
  scope is ``"local"``.
- `envs` - Extra environment variables.
- `timeout` - Command timeout in seconds.
  

**Returns**:

  Config value or ``None``.

<a id="wrenn._git.Git.configure_user"></a>

#### configure\_user

```python
def configure_user(name: str,
                   email: str,
                   *,
                   scope: str = "global",
                   cwd: str | None = None,
                   envs: dict[str, str] | None = None,
                   timeout: int | None = 30) -> None
```

Configure git user name and email.

**Arguments**:

- `name` - Git user name.
- `email` - Git user email.
- `scope` - Config scope. Defaults to ``"global"``.
- `cwd` - Working directory (repository root). Required when
  scope is ``"local"``.
- `envs` - Extra environment variables.
- `timeout` - Command timeout in seconds.
  

**Raises**:

- `ValueError` - If *name* or *email* is empty.
- `GitCommandError` - If a config command failed.

<a id="wrenn._git.Git.dangerously_authenticate"></a>

#### dangerously\_authenticate

```python
def dangerously_authenticate(username: str,
                             password: str,
                             host: str = "github.com",
                             protocol: str = "https",
                             *,
                             cwd: str | None = None,
                             envs: dict[str, str] | None = None,
                             timeout: int | None = 30) -> None
```

Persist git credentials via the credential store.

.. warning::

Credentials are written in plain text to the capsule
filesystem and are accessible to any process running inside
the capsule.  Prefer per-operation ``username``/``password``
parameters on :meth:`clone`, :meth:`push`, and :meth:`pull`
instead.

**Arguments**:

- `username` - Git username.
- `password` - Password or personal access token.
- `host` - Target host. Defaults to ``"github.com"``.
- `protocol` - Protocol. Defaults to ``"https"``.
- `cwd` - Working directory.
- `envs` - Extra environment variables.
- `timeout` - Command timeout in seconds.
  

**Raises**:

- `ValueError` - If *username* or *password* is empty.
- `GitCommandError` - If a command failed.

<a id="wrenn._git.AsyncGit"></a>

## AsyncGit Objects

```python
class AsyncGit()
```

Async git interface. Accessed via ``capsule.git``.

Async mirror of :class:`Git`. See that class for full method
documentation.

<a id="wrenn._git.AsyncGit.clone"></a>

#### clone

```python
async def clone(url: str,
                dest: str | None = None,
                *,
                branch: str | None = None,
                depth: int | None = None,
                username: str | None = None,
                password: str | None = None,
                dangerously_store_credentials: bool = False,
                cwd: str | None = None,
                envs: dict[str, str] | None = None,
                timeout: int | None = 300) -> CommandResult
```

Clone a remote repository into the capsule.

<a id="wrenn._git.AsyncGit.init"></a>

#### init

```python
async def init(path: str = ".",
               *,
               bare: bool = False,
               initial_branch: str | None = None,
               cwd: str | None = None,
               envs: dict[str, str] | None = None,
               timeout: int | None = 30) -> CommandResult
```

Initialize a new git repository.

<a id="wrenn._git.AsyncGit.add"></a>

#### add

```python
async def add(paths: list[str] | None = None,
              *,
              all: bool = False,
              cwd: str | None = None,
              envs: dict[str, str] | None = None,
              timeout: int | None = 30) -> CommandResult
```

Stage files for commit.

<a id="wrenn._git.AsyncGit.commit"></a>

#### commit

```python
async def commit(message: str,
                 *,
                 allow_empty: bool = False,
                 author_name: str | None = None,
                 author_email: str | None = None,
                 cwd: str | None = None,
                 envs: dict[str, str] | None = None,
                 timeout: int | None = 30) -> CommandResult
```

Create a commit.

<a id="wrenn._git.AsyncGit.push"></a>

#### push

```python
async def push(remote: str = "origin",
               branch: str | None = None,
               *,
               force: bool = False,
               set_upstream: bool = False,
               username: str | None = None,
               password: str | None = None,
               cwd: str | None = None,
               envs: dict[str, str] | None = None,
               timeout: int | None = 60) -> CommandResult
```

Push commits to a remote.

<a id="wrenn._git.AsyncGit.pull"></a>

#### pull

```python
async def pull(remote: str = "origin",
               branch: str | None = None,
               *,
               rebase: bool = False,
               ff_only: bool = False,
               username: str | None = None,
               password: str | None = None,
               cwd: str | None = None,
               envs: dict[str, str] | None = None,
               timeout: int | None = 60) -> CommandResult
```

Pull changes from a remote.

<a id="wrenn._git.AsyncGit.status"></a>

#### status

```python
async def status(*,
                 cwd: str | None = None,
                 envs: dict[str, str] | None = None,
                 timeout: int | None = 30) -> GitStatus
```

Get repository status.

<a id="wrenn._git.AsyncGit.branches"></a>

#### branches

```python
async def branches(*,
                   cwd: str | None = None,
                   envs: dict[str, str] | None = None,
                   timeout: int | None = 30) -> list[GitBranch]
```

List local branches.

<a id="wrenn._git.AsyncGit.create_branch"></a>

#### create\_branch

```python
async def create_branch(name: str,
                        *,
                        start_point: str | None = None,
                        cwd: str | None = None,
                        envs: dict[str, str] | None = None,
                        timeout: int | None = 30) -> CommandResult
```

Create and check out a new branch.

<a id="wrenn._git.AsyncGit.checkout_branch"></a>

#### checkout\_branch

```python
async def checkout_branch(name: str,
                          *,
                          cwd: str | None = None,
                          envs: dict[str, str] | None = None,
                          timeout: int | None = 30) -> CommandResult
```

Check out an existing branch.

<a id="wrenn._git.AsyncGit.delete_branch"></a>

#### delete\_branch

```python
async def delete_branch(name: str,
                        *,
                        force: bool = False,
                        cwd: str | None = None,
                        envs: dict[str, str] | None = None,
                        timeout: int | None = 30) -> CommandResult
```

Delete a branch.

<a id="wrenn._git.AsyncGit.remote_add"></a>

#### remote\_add

```python
async def remote_add(name: str,
                     url: str,
                     *,
                     fetch: bool = False,
                     cwd: str | None = None,
                     envs: dict[str, str] | None = None,
                     timeout: int | None = 30) -> CommandResult
```

Add a remote.

<a id="wrenn._git.AsyncGit.remote_get"></a>

#### remote\_get

```python
async def remote_get(name: str = "origin",
                     *,
                     cwd: str | None = None,
                     envs: dict[str, str] | None = None,
                     timeout: int | None = 30) -> str | None
```

Get the URL of a remote. Returns ``None`` if not found.

<a id="wrenn._git.AsyncGit.reset"></a>

#### reset

```python
async def reset(*,
                mode: str | None = None,
                ref: str | None = None,
                paths: list[str] | None = None,
                cwd: str | None = None,
                envs: dict[str, str] | None = None,
                timeout: int | None = 30) -> CommandResult
```

Reset the current HEAD.

<a id="wrenn._git.AsyncGit.restore"></a>

#### restore

```python
async def restore(paths: list[str],
                  *,
                  staged: bool = False,
                  worktree: bool = False,
                  source: str | None = None,
                  cwd: str | None = None,
                  envs: dict[str, str] | None = None,
                  timeout: int | None = 30) -> CommandResult
```

Restore working-tree files or unstage changes.

<a id="wrenn._git.AsyncGit.set_config"></a>

#### set\_config

```python
async def set_config(key: str,
                     value: str,
                     *,
                     scope: str = "local",
                     cwd: str | None = None,
                     envs: dict[str, str] | None = None,
                     timeout: int | None = 30) -> CommandResult
```

Set a git config value.

<a id="wrenn._git.AsyncGit.get_config"></a>

#### get\_config

```python
async def get_config(key: str,
                     *,
                     scope: str = "local",
                     cwd: str | None = None,
                     envs: dict[str, str] | None = None,
                     timeout: int | None = 30) -> str | None
```

Get a git config value. Returns ``None`` if not set.

<a id="wrenn._git.AsyncGit.configure_user"></a>

#### configure\_user

```python
async def configure_user(name: str,
                         email: str,
                         *,
                         scope: str = "global",
                         cwd: str | None = None,
                         envs: dict[str, str] | None = None,
                         timeout: int | None = 30) -> None
```

Configure git user name and email.

<a id="wrenn._git.AsyncGit.dangerously_authenticate"></a>

#### dangerously\_authenticate

```python
async def dangerously_authenticate(username: str,
                                   password: str,
                                   host: str = "github.com",
                                   protocol: str = "https",
                                   *,
                                   cwd: str | None = None,
                                   envs: dict[str, str] | None = None,
                                   timeout: int | None = 30) -> None
```

Persist git credentials via the credential store.

.. warning::

Credentials are written in plain text to the capsule
filesystem.  Prefer per-operation ``username``/``password``
parameters instead.

