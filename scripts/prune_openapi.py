"""Prune the upstream Wrenn OpenAPI spec down to the SDK's surface.

The upstream spec at ``wrennhq/wrenn/internal/api/openapi.yaml`` covers
the whole control plane: account/team/host/channel/admin routes that
require an interactive ``wrenn_sid`` cookie. The Python SDK only ever
authenticates with an API key, so those routes are dead surface area
here. This script keeps only paths that list ``apiKeyAuth`` (and the
schemas they transitively reach) and rewrites the spec in place.

Run via ``make generate`` (curl ➜ prune ➜ datamodel-codegen) or
``uv run python scripts/prune_openapi.py [path]`` directly.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

KEEP_PATHS: set[str] = {
    "/v1/capsules",
    "/v1/capsules/stats",
    "/v1/capsules/usage",
    "/v1/capsules/{id}",
    "/v1/capsules/{id}/exec",
    "/v1/capsules/{id}/exec/stream",
    "/v1/capsules/{id}/processes",
    "/v1/capsules/{id}/processes/{selector}",
    "/v1/capsules/{id}/processes/{selector}/stream",
    "/v1/capsules/{id}/ping",
    "/v1/capsules/{id}/metrics",
    "/v1/capsules/{id}/pause",
    "/v1/capsules/{id}/resume",
    "/v1/capsules/{id}/files/write",
    "/v1/capsules/{id}/files/read",
    "/v1/capsules/{id}/files/list",
    "/v1/capsules/{id}/files/mkdir",
    "/v1/capsules/{id}/files/remove",
    "/v1/capsules/{id}/files/stream/write",
    "/v1/capsules/{id}/files/stream/read",
    "/v1/capsules/{id}/pty",
    "/v1/snapshots",
    "/v1/snapshots/{name}",
    "/v1/events/stream",
}

KEEP_SECURITY_SCHEMES: set[str] = {"apiKeyAuth"}

REF_RE = re.compile(r"#/components/(schemas|responses)/([A-Za-z0-9_]+)")


def _walk_refs(node: object, schemas: dict, responses: dict, seen: set[str]) -> None:
    """Depth-first walk collecting ``schemas:Name`` / ``responses:Name`` refs."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "$ref" and isinstance(v, str):
                m = REF_RE.search(v)
                if m:
                    kind, name = m.group(1), m.group(2)
                    key = f"{kind}:{name}"
                    if key in seen:
                        continue
                    seen.add(key)
                    target = (schemas if kind == "schemas" else responses).get(name)
                    if target is not None:
                        _walk_refs(target, schemas, responses, seen)
            else:
                _walk_refs(v, schemas, responses, seen)
    elif isinstance(node, list):
        for item in node:
            _walk_refs(item, schemas, responses, seen)


def _filter_security(operation: dict) -> None:
    sec = operation.get("security")
    if not isinstance(sec, list):
        return
    kept = [
        entry
        for entry in sec
        if isinstance(entry, dict)
        and any(name in KEEP_SECURITY_SCHEMES for name in entry)
    ]
    if kept:
        operation["security"] = kept
    else:
        operation.pop("security", None)


def prune(spec: dict) -> dict:
    paths = spec.get("paths", {})
    components = spec.get("components", {})
    schemas = components.get("schemas", {}) or {}
    responses = components.get("responses", {}) or {}

    missing = KEEP_PATHS - set(paths)
    if missing:
        raise SystemExit(
            "prune_openapi: upstream spec is missing expected paths: "
            + ", ".join(sorted(missing))
        )

    kept_paths: dict[str, dict] = {}
    for path, item in paths.items():
        if path not in KEEP_PATHS:
            continue
        if not isinstance(item, dict):
            kept_paths[path] = item
            continue
        for method, op in list(item.items()):
            if isinstance(op, dict):
                _filter_security(op)
                if "security" in op and not op["security"]:
                    del item[method]
        kept_paths[path] = item

    seen: set[str] = set()
    _walk_refs(kept_paths, schemas, responses, seen)

    # Walk again to close over inter-schema refs we just pulled in.
    while True:
        before = len(seen)
        for key in list(seen):
            kind, name = key.split(":", 1)
            target = (schemas if kind == "schemas" else responses).get(name)
            if target is not None:
                _walk_refs(target, schemas, responses, seen)
        if len(seen) == before:
            break

    kept_schemas = {n: schemas[n] for n in schemas if f"schemas:{n}" in seen}
    kept_responses = {n: responses[n] for n in responses if f"responses:{n}" in seen}

    sec_schemes = components.get("securitySchemes", {}) or {}
    kept_sec_schemes = {
        n: sec_schemes[n] for n in sec_schemes if n in KEEP_SECURITY_SCHEMES
    }

    new_components: dict = {}
    if kept_responses:
        new_components["responses"] = kept_responses
    if kept_sec_schemes:
        new_components["securitySchemes"] = kept_sec_schemes
    if kept_schemas:
        new_components["schemas"] = kept_schemas

    spec["paths"] = kept_paths
    spec["components"] = new_components

    top_security = spec.get("security")
    if isinstance(top_security, list):
        spec["security"] = [
            e
            for e in top_security
            if isinstance(e, dict) and any(name in KEEP_SECURITY_SCHEMES for name in e)
        ]

    return spec


def main(argv: list[str]) -> int:
    target = Path(argv[1]) if len(argv) > 1 else Path("api/openapi.yaml")
    spec = yaml.safe_load(target.read_text())
    pruned = prune(spec)
    target.write_text(
        yaml.safe_dump(pruned, sort_keys=False, width=120, allow_unicode=True)
    )
    print(
        f"prune_openapi: kept {len(pruned['paths'])} paths, "
        f"{len(pruned['components'].get('schemas', {}))} schemas in {target}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
