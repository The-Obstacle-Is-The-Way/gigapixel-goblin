.PHONY: install install-system test test-watch test-cov lint format format-check typecheck check all clean download-data benchmark mutmut

install:
	uv sync

install-system:
	@echo "Installing system dependencies..."
	@echo "Note: openslide-bin pip package now auto-installs OpenSlide binaries"
	@echo "Manual install only needed if openslide-bin fails:"
	@if [ "$$(uname)" = "Darwin" ]; then \
		brew install openslide; \
	elif [ -f /etc/debian_version ]; then \
		sudo apt-get install -y openslide-tools; \
	fi

test:
	uv run pytest -m "not live and not cost"

test-watch:
	uv run ptw -- -m "not live and not cost" --maxfail=1

test-cov:
	uv run pytest -m "not live and not cost" --cov=src/giant --cov-report=html --cov-fail-under=90

test-live:
	GIANT_RUN_LIVE_TESTS=1 uv run pytest -m "live or cost"

test-all:
	GIANT_RUN_LIVE_TESTS=1 uv run pytest

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
	uv run giant benchmark $(or $(DATASET),tcga) --csv-path data/multipathqa/MultiPathQA.csv --wsi-root data/wsi --output-dir results

benchmark-tcga:
	$(MAKE) benchmark DATASET=tcga

benchmark-gtex:
	$(MAKE) benchmark DATASET=gtex

benchmark-panda:
	$(MAKE) benchmark DATASET=panda

mutmut:
	uv run mutmut run

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +

all: format check
