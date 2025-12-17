# Spec-01: Project Foundation & Tooling

## Overview
This specification establishes the modern Python project structure, dependency management, and quality assurance tooling required for the GIANT framework. It sets the groundwork for a robust, production-grade codebase using 2025 best practices.

## Dependencies
None.

## Acceptance Criteria
- [ ] `pyproject.toml` is configured with `uv` as the package manager and includes all initial dependencies.
- [ ] `uv.lock` is generated and committed for reproducible installs; CI uses `uv sync --locked`.
- [ ] Project directory structure follows the `src` layout standard.
- [ ] `Makefile` exists and successfully runs `install`, `test`, `lint`, `format`, `check`, `download-data`, `benchmark`, `clean` and `mutmut` targets.
- [ ] `pytest` is configured with `pytest-sugar`, `pytest-cov`, `pytest-xdist`, `pytest-asyncio`, `pytest-randomly`, `pytest-watch`, and a dummy test passes.
- [ ] `mypy` is configured in `pyproject.toml` with `strict = true` and passes on the skeleton code.
- [ ] `ruff` is configured for both linting and formatting, replacing `black` and `isort`.
- [ ] Pre-commit hooks are installed and pass locally.
- [ ] Structured logging is implemented using `structlog`.
- [ ] Settings management is implemented using `pydantic-settings` with `.env` support.
- [ ] `.github/workflows/ci.yml` is created with matrix testing and cache.
- [ ] `.github/workflows/codeql.yml` is created for CodeQL scanning.
- [ ] `.github/workflows/release.yml` is created for tag-based releases (PyPI publishing via Trusted Publishing).
- [ ] `.github/dependabot.yml` is created for dependency update PRs.
- [ ] PR + issue templates are added under `.github/`.

## Technical Design

### Directory Structure
```text
gigapixel-goblin/
├── .github/
│   ├── dependabot.yml
│   ├── pull_request_template.md
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.yml
│   │   └── feature_request.yml
│   └── workflows/
│       ├── ci.yml
│       ├── codeql.yml
│       └── release.yml
├── docs/
│   └── specs/
├── src/
│   └── giant/
│       ├── __init__.py
│       ├── config.py
│       ├── py.typed
│       └── utils/
│           ├── __init__.py
│           └── logging.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── unit/
│       └── test_config.py
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── Makefile
├── pyproject.toml
├── uv.lock
└── README.md
```

### Dependency Management (uv)
We use `uv` for extremely fast dependency resolution and installation.
**`pyproject.toml` configuration:**
```toml
[project]
name = "giant"
version = "0.1.0"
description = "Gigapixel Image Agent for Navigating Tissue"
requires-python = ">=3.11"
dependencies = [
    # Core WSI handling (Dec 2025: v1.4.3)
    "openslide-python>=1.4.3",
    "openslide-bin>=4.0.0.10",
    # Config & validation
    "pydantic>=2.12.5",
    "pydantic-settings>=2.12.0",
    "structlog>=25.5.0",
    # CLI (Dec 2025: v0.20.0)
    "typer>=0.20.0",
    # Numerics
    # NOTE: `opencv-python` 4.12.0.88 pins NumPy <2.3.0
    "numpy>=2.2.6,<2.3.0",
    "pillow>=12.0.0",
    # LLM APIs
    "anthropic>=0.75.0",
    "openai>=2.13.0",
    "tenacity>=9.1.2",
    "httpx>=0.28.1",  # Async HTTP for API clients
    # Data & HuggingFace (Dec 2025: datasets v4.4.1)
    "datasets>=4.4.1",
    "huggingface_hub>=1.2.3",
    # Computer Vision (for CLAM-style segmentation)
    "opencv-python>=4.12.0.88",
    "scipy>=1.16.3",
    "scikit-image>=0.25.2",
    # Caching (persistent crop/metadata cache)
    "diskcache>=5.6.3",
    # Rate limiting for concurrent API calls
    "aiolimiter>=1.2.1",
    # DevEx
    "rich>=14.2.0",
    "tqdm>=4.67.1",
]

[dependency-groups]
dev = [
    "pytest>=9.0.2",
    "pytest-cov>=7.0.0",
    "pytest-sugar>=1.1.1",
    "pytest-xdist>=3.8.0",
    "pytest-asyncio>=1.3.0",
    "pytest-randomly>=4.0.1",
    "pytest-watch>=4.2.0",
    "pytest-timeout>=2.4.0",  # Prevent hanging tests (OpenSlide + async)
    "pytest-benchmark>=5.2.3",  # Performance regression tests
    "mutmut>=3.4.0",  # Mutation testing
    "hypothesis>=6.148.7",
    "respx>=0.22.0",  # Mock httpx requests for LLM tests
    "tifffile>=2025.12.12",  # Create synthetic TIFF test assets
    "polyfactory>=3.1.0",
    "faker>=38.2.0",
    "mypy>=1.19.1",
    "ruff>=0.14.9",
    "pre-commit>=4.5.1",
    "types-Pillow>=10.2.0.20240822",
]
```

**Note:** `openslide-python` does not have official type stubs. Use inline type annotations with `# type: ignore` for OpenSlide calls, or create local stubs in `src/giant/stubs/`.

### Code Quality Tools

#### Ruff (Linting & Formatting)
Ruff replaces `black`, `isort`, and `flake8`.
**`pyproject.toml` configuration:**
```toml
[tool.ruff]
line-length = 88
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "B", "I", "N", "UP", "PL", "RUF"]
ignore = []

[tool.ruff.format]
quote-style = "double"
```

#### Mypy (Static Type Checking)
Strict mode is mandatory.
**`pyproject.toml` configuration:**
```toml
[tool.mypy]
strict = true
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

#### Pytest + Coverage
Keep the test pyramid healthy (unit-heavy, minimal live API tests).
**`pyproject.toml` configuration:**
```toml
[tool.pytest.ini_options]
minversion = "9.0"
testpaths = ["tests"]
addopts = "-ra"
markers = [
  "cost: live API tests (opt-in, may spend money)",
]
asyncio_mode = "auto"

[tool.coverage.run]
branch = true
source = ["giant"]

[tool.coverage.report]
fail_under = 90
show_missing = true
skip_covered = true

[tool.mutmut]
paths_to_mutate = ["src/giant"]
pytest_add_cli_args = ["-q"]
pytest_add_cli_args_test_selection = ["tests/unit"]
```

#### Build System (Packaging)
Use a modern PEP 517 build backend so `uv build` works in CI/release workflows.
```toml
[build-system]
requires = ["hatchling>=1.28.0"]
build-backend = "hatchling.build"
```

### Logging (structlog)
Structured logging is essential for observability of the agent's reasoning traces.
`src/giant/utils/logging.py` will configure `structlog` to output JSON in production and colored console output in development.

**Correlation IDs (Required):** Use `contextvars` to attach `run_id`, `item_id` (benchmark row), and `step` to every log line to support tracing/debugging across concurrent runs.

### Configuration (Pydantic Settings)
All configuration must be strongly typed.
`src/giant/config.py`:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    HUGGINGFACE_TOKEN: str | None = None
    LOG_LEVEL: str = "INFO"

    # Paper Parameters
    WSI_LONG_SIDE_TARGET: int = 1000  # S parameter
    MAX_ITERATIONS: int = 20  # T parameter
    OVERSAMPLING_BIAS: float = 0.85
    THUMBNAIL_SIZE: int = 1024  # Paper baseline

    # Baselines
    PATCH_SIZE: int = 224
    PATCH_COUNT: int = 30

    # Evaluation
    BOOTSTRAP_REPLICATES: int = 1000

    # Image Generation
    JPEG_QUALITY: int = 85
    # Per-provider image sizes (paper uses 500px for Claude due to pricing)
    IMAGE_SIZE_OPENAI: int = 1000
    IMAGE_SIZE_ANTHROPIC: int = 500

settings = Settings()
```

## Test Plan

### Unit Tests
1.  **Config Test:** Verify that settings are loaded correctly from env vars and defaults.
2.  **Logging Test:** Verify that the logger produces valid JSON/structured output.

### Integration Tests
N/A for this foundation spec.

## File Structure & Content

### `.env.example`
```ini
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
HUGGINGFACE_TOKEN=
LOG_LEVEL=INFO
```

### `Makefile`
```makefile
.PHONY: install install-system test test-watch test-cov lint format format-check typecheck check all clean download-data benchmark mutmut

install:
	uv sync

install-system:
	@echo "Installing system dependencies..."
	@echo "Note: openslide-bin pip package now auto-installs OpenSlide binaries"
	@echo "Manual install only needed if openslide-bin fails:"
	@if [ "$(shell uname)" = "Darwin" ]; then \
		brew install openslide; \
	elif [ -f /etc/debian_version ]; then \
		sudo apt-get install -y openslide-tools; \
	fi

test:
	uv run pytest

test-watch:
	uv run ptw -- --maxfail=1

test-cov:
	uv run pytest --cov=src/giant --cov-report=html --cov-fail-under=90

lint:
	uv run ruff check .

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

typecheck:
	uv run mypy src

check: lint typecheck test

download-data:
	uv run python -m giant.data.download

benchmark:
	uv run giant benchmark ./data/multipathqa --output-dir ./results

mutmut:
	uv run mutmut run

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +

all: format check
```

### `.github/workflows/ci.yml`
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v7
        with:
          version: "0.9.18"
          python-version: ${{ matrix.python-version }}
          enable-cache: true
          cache-suffix: ${{ matrix.python-version }}
          cache-dependency-glob: |
            pyproject.toml
            uv.lock

      - name: Install system deps
        run: |
          sudo apt-get update
          sudo apt-get install -y openslide-tools

      - name: Install dependencies
        run: uv sync --locked

      - name: Format check
        run: uv run ruff format --check .

      - name: Lint
        run: uv run ruff check .

      - name: Type check
        run: uv run mypy src

      - name: Test with coverage
        run: uv run pytest --cov=src/giant --cov-report=xml --cov-fail-under=90

      - name: Upload coverage
        uses: codecov/codecov-action@v5
        with:
          files: coverage.xml
          fail_ci_if_error: true
```

### `.github/workflows/codeql.yml`
```yaml
name: CodeQL

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: "0 3 * * 1"

jobs:
  analyze:
    runs-on: ubuntu-latest
    permissions:
      actions: read
      contents: read
      security-events: write

    steps:
      - uses: actions/checkout@v4
      - uses: github/codeql-action/init@v3
        with:
          languages: python
      - uses: github/codeql-action/analyze@v3
```

### `.github/workflows/release.yml`
```yaml
name: Release

on:
  push:
    tags: ["v*"]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v7
        with:
          version: "0.9.18"
          python-version: "3.12"
          enable-cache: true
          cache-dependency-glob: |
            pyproject.toml
            uv.lock

      - name: Build distributions
        run: uv build --no-sources

      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/*

  publish:
    needs: build
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@v1.13.0
        with:
          packages-dir: dist
```

### `.github/dependabot.yml`
```yaml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    groups:
      github-actions:
        patterns: ["*"]

  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10
```

### `.pre-commit-config.yaml`
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-merge-conflict
      - id: detect-private-key
      - id: check-added-large-files
        args: ["--maxkb=2048"]

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.9
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: local
    hooks:
      - id: uv-lock-check
        name: uv lock --check
        entry: uv lock --check
        language: system
        pass_filenames: false

      - id: mypy
        name: mypy (uv)
        entry: uv run mypy src
        language: system
        pass_filenames: false
```

### `.github/pull_request_template.md`
```markdown
## Summary
-

## Test Plan
- [ ] `make check`
- [ ] Unit tests added/updated

## Checklist
- [ ] No hardcoded secrets
- [ ] Logging is structured and non-PHI by default
- [ ] Spec acceptance criteria met
```

### `.github/ISSUE_TEMPLATE/bug_report.yml`
```yaml
name: Bug report
description: Report a problem in GIANT
title: "bug: "
labels: ["bug"]
body:
  - type: textarea
    id: what-happened
    attributes:
      label: What happened?
      description: Include error messages and a short description.
    validations:
      required: true

  - type: textarea
    id: steps
    attributes:
      label: Steps to reproduce
      description: Provide a minimal repro if possible.

  - type: textarea
    id: logs
    attributes:
      label: Logs
      render: text

  - type: input
    id: version
    attributes:
      label: GIANT version

  - type: input
    id: python
    attributes:
      label: Python version
```

### `.github/ISSUE_TEMPLATE/feature_request.yml`
```yaml
name: Feature request
description: Suggest an enhancement
title: "feat: "
labels: ["enhancement"]
body:
  - type: textarea
    id: problem
    attributes:
      label: Problem statement
      description: What problem are you trying to solve?
    validations:
      required: true

  - type: textarea
    id: proposal
    attributes:
      label: Proposed solution

  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives considered
```

### Branch Protection (Documented Policy)
Configure GitHub branch protection for `main`:
- Require status checks: `CI`, `CodeQL`
- Require 1+ approvals
- Require linear history (optional)
- Require conversation resolution
- Restrict who can push to `main`

### `Dockerfile` (Optional, Production-Readiness)
If the project is deployed as a service or run reproducibly in a container, provide a minimal Dockerfile.
```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \\
    openslide-tools \\
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir uv==0.9.18

COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-dev --no-install-project

COPY src /app/src

RUN uv sync --frozen --no-dev

ENTRYPOINT ["giant"]
```

### `.dockerignore` (Optional)
```text
.git
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
htmlcov/
dist/
*.egg-info/
.venv/
data/
results/
```

## API Reference
N/A
