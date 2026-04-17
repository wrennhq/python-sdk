from __future__ import annotations

from wrenn.client import WrennClient

from .conftest import requires_auth


@requires_auth
class TestSnapshots:
    def test_list_templates(self, client: WrennClient):
        templates = client.snapshots.list()
        assert isinstance(templates, list)


@requires_auth
class TestAPIKeys:
    def test_create_list_delete(self, bearer_client: WrennClient):
        key_resp = bearer_client.api_keys.create(name="integration-test-key")
        assert key_resp.name == "integration-test-key"
        assert key_resp.key is not None
        assert key_resp.id is not None

        try:
            keys = bearer_client.api_keys.list()
            ids = [k.id for k in keys]
            assert key_resp.id in ids
        finally:
            bearer_client.api_keys.delete(key_resp.id)
