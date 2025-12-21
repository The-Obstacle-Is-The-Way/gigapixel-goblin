# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## CRITICAL: Model Registry is Immutable

**NEVER modify the model IDs in `docs/models/MODEL_REGISTRY.md` or `src/giant/llm/model_registry.py`.**

The models `gpt-5.2`, `claude-sonnet-4-5-20250929`, and `gemini-3-pro-preview` are real 2025 frontier models. They have been validated and are correct. Do not assume they are fictional or outdated. Do not "fix" them.

## Project Overview

GIANT (Gigapixel Image Agent for Navigating Tissue) is an agentic system that uses LLMs to autonomously navigate whole-slide images (WSI) for pathology analysis. The agent iteratively crops regions based on LLM decisions until it can answer a question about the slide.

## Commands

```bash
# Setup
uv sync                           # Install dependencies
source .venv/bin/activate         # Activate virtual environment

# Testing
pytest tests/unit                 # Run unit tests only
pytest tests/unit -x             # Stop on first failure
pytest tests/unit/llm/            # Run specific module tests
pytest -k "test_name"             # Run single test by name
pytest --cov=giant --cov-report=term-missing  # With coverage

# Linting and Formatting
ruff check .                      # Lint
ruff format .                     # Format
mypy src/giant                    # Type check (strict mode enabled)

# CLI Usage
giant version                     # Show version
giant run <wsi_path> -q "What tissue is this?"  # Run on single WSI
giant benchmark tcga --max-items=10             # Run benchmark subset
giant check-data tcga                           # Validate WSI files exist
giant download multipathqa                      # Download benchmark CSV
```

## Architecture

### Core Flow (Algorithm 1 from GIANT paper)
1. `GIANTAgent` opens WSI via `WSIReader` and generates thumbnail with axis guides
2. LLM examines thumbnail and outputs structured JSON: `{reasoning, action}`
3. If `action.type == "crop"`: `CropEngine` extracts region, loop continues
4. If `action.type == "answer"`: navigation ends with final answer
5. `ContextManager` maintains multi-turn conversation history
6. `Trajectory` records all steps for evaluation and visualization

### Key Modules

**`src/giant/agent/`** - Agent orchestration
- `runner.py`: `GIANTAgent` class - main navigation loop with retry logic
- `context.py`: `ContextManager` - multi-turn conversation state
- `trajectory.py`: Step recording for evaluation

**`src/giant/llm/`** - LLM abstraction layer
- `protocol.py`: `LLMProvider` Protocol, `Message`, `StepResponse`, `Action` types
- `openai_client.py`: OpenAI Responses API implementation
- `anthropic_client.py`: Anthropic Messages API implementation
- `converters.py`: Transform between internal and provider-specific formats
- `model_registry.py`: Approved model IDs (enforced at runtime)

**`src/giant/core/`** - WSI processing
- `crop_engine.py`: Region extraction with pyramid level selection
- `level_selector.py`: Optimal resolution selection algorithm

**`src/giant/geometry/`** - Coordinate handling
- `primitives.py`: `Region`, `Point`, `Size` value objects
- `overlay.py`: Axis guide rendering for LLM context
- `validators.py`: Bounds checking for crop coordinates

**`src/giant/prompts/`** - Prompt engineering
- `builder.py`: `PromptBuilder` assembles system/user prompts per step
- `templates.py`: Navigation prompt templates

### LLM Provider Pattern

Providers implement `LLMProvider` Protocol with `generate_response()` async method. Factory function creates instances:

```python
from giant.llm import create_provider
provider = create_provider("openai", model="gpt-5.2")
# or
provider = create_provider("anthropic", model="claude-sonnet-4-5-20250929")
```

### Model Registry

Only approved models in `docs/models/MODEL_REGISTRY.md` are allowed. Runtime enforcement in `src/giant/llm/model_registry.py`. Current frontier models (2025):
- OpenAI: `gpt-5.2`
- Anthropic: `claude-sonnet-4-5-20250929`
- Google: `gemini-3-pro-preview`

## Testing Conventions

- **Unit tests**: `tests/unit/` - Fast, no external dependencies, use mocks
- **Integration tests**: `tests/integration/` - Real WSI files or live API calls
- Markers: `@pytest.mark.cost` (live API), `@pytest.mark.integration` (real WSI)
- Coverage target: 90% (enforced in CI)
- TDD required: write failing tests first

## Specs and Bugs

- `docs/specs/`: Implementation specifications (Spec-01 through Spec-12)
- `docs/bugs/`: Bug documentation with root cause analysis
- Integration checkpoints at Spec-05.5, Spec-08.5, Spec-11.5 are mandatory pause points

## WSI Data Requirements

MultiPathQA benchmark requires ~862 WSI files (~500+ GiB):
- TCGA: 474 `.svs` files
- GTEx: 191 `.tiff` files
- PANDA: 197 `.tiff` files

See `docs/DATA_ACQUISITION.md` for download instructions.
