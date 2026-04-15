# Makefile
.PHONY: generate lint test check test-integration

# Variables
SPEC_URL = "https://git.omukk.dev/wrenn/wrenn/raw/branch/dev/internal/api/openapi.yaml"
SPEC_PATH = "api/openapi.yaml"

generate:
	@echo "Fetching latest OpenAPI spec from Git repo..."

	mkdir -p api

	curl -fsSL $(SPEC_URL) -o $(SPEC_PATH)

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
	uv run pytest tests/test_client.py -v

test-integration:
	uv run pytest tests/ -v -m "integration or not integration"

check: lint test
