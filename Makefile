# Makefile
.PHONY: generate gen-docs lint test check test-integration test-code-runner prune-spec

# Variables
SPEC_URL = "https://raw.githubusercontent.com/wrennhq/wrenn/refs/heads/main/internal/api/openapi.yaml"
SPEC_PATH = "api/openapi.yaml"

generate:
	@echo "Fetching latest OpenAPI spec from Git repo..."

	mkdir -p api

	curl -fsSL $(SPEC_URL) -o $(SPEC_PATH)

	$(MAKE) prune-spec

	uv run datamodel-codegen \
		--input $(SPEC_PATH) \
		--output src/wrenn/models/_generated.py \
		--output-model-type pydantic_v2.BaseModel \
		--snake-case-field \
		--field-constraints \
		--use-schema-description \
		--target-python-version 3.13 \
		--use-annotated \
		--openapi-scopes schemas \
		--formatters ruff-format ruff-check \
		--input-file-type openapi

lint:
	uv run ruff check src/
	uv run ruff format --check src/

test:
	uv run pytest tests/test_client.py tests/test_code_runner_unit.py -v

test-integration:
	uv run pytest tests/ -v -m "integration or not integration" --ignore=tests/test_code_runner_e2e.py --ignore=tests/test_code_runner_unit.py

test-code-runner:
	uv run pytest tests/test_code_runner_unit.py tests/test_code_runner_e2e.py -v -m "integration or not integration"

check: lint test

prune-spec:
	@echo "Pruning spec down to the SDK's API-key surface..."
	uv run python scripts/prune_openapi.py $(SPEC_PATH)

gen-docs:
	mkdir -p docs
	uv run pydoc-markdown > docs/reference.md
