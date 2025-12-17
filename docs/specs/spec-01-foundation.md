# Spec-01: Project Foundation & Tooling

## Overview
This specification establishes the modern Python project structure, dependency management, and quality assurance tooling required for the GIANT framework. It sets the groundwork for a robust, production-grade codebase using 2025 best practices.

## Dependencies
None.

## Acceptance Criteria
- [ ] `pyproject.toml` is configured with `uv` as the package manager and includes all initial dependencies.
- [ ] Project directory structure follows the `src` layout standard.
- [ ] `Makefile` exists and successfully runs `install`, `test`, `lint`, `format`, `check`, `download-data`, `benchmark`, `clean` and `mutmut` targets.
- [ ] `pytest` is configured with `pytest-sugar`, `pytest-cov`, `pytest-xdist`, `pytest-asyncio`, `pytest-randomly`, `pytest-watch`, and a dummy test passes.
- [ ] `mypy` is configured in `pyproject.toml` with `strict = true` and passes on the skeleton code.
- [ ] `ruff` is configured for both linting and formatting, replacing `black` and `isort`.
- [ ] Pre-commit hooks are installed and pass locally.
- [ ] Structured logging is implemented using `structlog`.
- [ ] Settings management is implemented using `pydantic-settings` with `.env` support.
- [ ] `.github/workflows/ci.yml` is created with matrix testing and cache.

## Technical Design

### Directory Structure
```text
gigapixel-goblin/
├── .github/
│   └── workflows/
│       └── ci.yml
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
    "openslide-python>=1.4.0",
    "openslide-bin>=4.0.0",  # Auto-installs OpenSlide binaries
    # Config & validation
    "pydantic>=2.9.0",
    "pydantic-settings>=2.9.0",
    "structlog>=24.4.0",
    # CLI (Oct 2025: v0.20.0)
    "typer>=0.15.0",
    # Numerics
    "numpy>=1.26.0",
    "pillow>=10.4.0",
    # LLM APIs
    "anthropic>=0.39.0",
    "openai>=1.55.0",
    "tenacity>=9.0.0",
    "httpx>=0.27.0",  # Async HTTP for API clients
    # Data & HuggingFace (Nov 2025: datasets v4.4.1)
    "datasets>=4.0.0",
    "huggingface_hub>=0.26.0",
    # Computer Vision (for CLAM-style segmentation)
    "opencv-python>=4.10.0",
    "scipy>=1.14.0",
    "scikit-image>=0.24.0",
    # Caching (persistent crop/metadata cache)
    "diskcache>=5.6.0",
    # Rate limiting for concurrent API calls
    "aiolimiter>=1.1.0",
    # DevEx
    "rich>=13.9.0",
    "tqdm>=4.66.0",
]

[dependency-groups]
dev = [
    "pytest>=8.3.0",
    "pytest-cov>=5.0.0",
    "pytest-sugar>=1.0.0",
    "pytest-xdist>=3.6.0",
    "pytest-asyncio>=0.24.0",
    "pytest-randomly>=3.15.0",
    "pytest-watch>=4.2.0",
    "pytest-timeout>=2.3.0",  # Prevent hanging tests (OpenSlide + async)
    "mutmut>=3.0.0",  # Mutation testing
    "hypothesis>=6.115.0",
    "respx>=0.21.0",  # Mock httpx requests for LLM tests
    "tifffile>=2024.8.0",  # Create synthetic TIFF test assets
    "mypy>=1.13.0",
    "ruff>=0.7.0",
    "pre-commit>=4.0.0",
    "types-Pillow>=10.2.0",
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

### Logging (structlog)
Structured logging is essential for observability of the agent's reasoning traces.
`src/giant/utils/logging.py` will configure `structlog` to output JSON in production and colored console output in development.

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
.PHONY: install install-system test test-watch test-cov lint format check all clean download-data benchmark mutmut

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
	uv run ptw -- --testmon

test-cov:
	uv run pytest --cov=src/giant --cov-report=html --cov-fail-under=90

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy src

check: lint typecheck test

download-data:
	uv run python -m giant.data.download

benchmark:
	uv run giant benchmark ./data/multipathqa --output-dir ./results

mutmut:
	uv run mutmut run --paths-to-mutate=src/giant

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
        uses: astral-sh/setup-uv@v4

      - name: Install system deps
        run: sudo apt-get install -y openslide-tools

      - name: Set up Python ${{ matrix.python-version }}
        run: uv python install ${{ matrix.python-version }}

      - name: Install dependencies
        run: uv sync

      - name: Lint
        run: uv run ruff check .

      - name: Type check
        run: uv run mypy src

      - name: Test with coverage
        run: uv run pytest --cov=src/giant --cov-report=xml --cov-fail-under=90

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml
```

## API Reference
N/A
