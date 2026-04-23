from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://app.wrenn.dev/api"
ENV_API_KEY = "WRENN_API_KEY"
ENV_BASE_URL = "WRENN_BASE_URL"


@dataclass(frozen=True)
class ConnectionConfig:
    """Resolved credentials and base URL for Wrenn API calls."""

    api_key: str
    base_url: str

    @classmethod
    def from_env(
        cls,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> ConnectionConfig:
        resolved_key = api_key or os.environ.get(ENV_API_KEY)
        if not resolved_key:
            raise ValueError(
                f"No API key provided. Pass api_key= or set the {ENV_API_KEY} environment variable."
            )
        resolved_url = base_url or os.environ.get(ENV_BASE_URL, DEFAULT_BASE_URL)
        return cls(api_key=resolved_key, base_url=resolved_url)

    def auth_headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key}
