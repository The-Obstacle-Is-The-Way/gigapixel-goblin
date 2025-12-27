# Gemini Context for Gigapixel Goblin (GIANT)

## Project Overview
**GIANT** (Gigapixel Image Agent for Navigating Tissue) is an agentic system that uses Large Language Models (LLMs) to autonomously navigate Whole-Slide Images (WSI) for pathology analysis. The agent iteratively crops regions based on visual feedback until it can answer a specific medical question about the slide.

## Development Environment

### Key Technologies
- **Language:** Python 3.11+
- **Dependency Management:** `uv`
- **WSI Handling:** `openslide-python`, `openslide-bin`
- **LLM Integration:** `openai`, `anthropic`, `httpx`
- **CLI:** `typer`
- **Validation:** `pydantic` (strict mode)
- **Testing:** `pytest`, `hypothesis`

### Build & Run Commands
The project uses a `Makefile` to wrap common `uv` commands.

- **Install Dependencies:** `make install` (uses `uv sync`)
- **Run Unit Tests:** `make test` (or `pytest tests/unit`)
- **Lint:** `make lint` (`uv run ruff check .`)
- **Format:** `make format` (`uv run ruff format .`)
- **Type Check:** `make typecheck` (`uv run mypy src` - **Strict Mode**)
- **Check All:** `make check` (Lint, Typecheck, Test)

## Architecture & Codebase Map

### Core Flow
1. **GIANTAgent:** The main loop. Opens a WSI, generates a thumbnail with axis guides.
2. **LLM Decision:** The LLM receives the image and decides to either `crop` (zoom in) or `answer`.
3. **CropEngine:** If `crop` is chosen, this engine extracts the region at a higher resolution.
4. **ContextManager:** Maintains the multi-turn conversation history.

### Key Directories
- `src/giant/agent/`: Core logic (`GIANTAgent`, `ContextManager`, `Trajectory`).
- `src/giant/llm/`: LLM abstraction (`LLMProvider` protocol, `OpenAIClient`, `AnthropicClient`).
- `src/giant/core/`: WSI processing (`CropEngine`, `PyramidLevelSelector`).
- `src/giant/geometry/`: Geometric primitives (`Region`, `Point`, `Size`).
- `src/giant/prompts/`: Prompt engineering and templates.
- `tests/unit/`: Fast, mocked unit tests (Primary testing ground).
- `tests/integration/`: Tests requiring real WSI files or APIs.
- `docs/specs/`: Detailed implementation specifications.

## Critical Rules & Conventions

### 1. Model Registry is Immutable
**NEVER modify the model IDs in `docs/models/model-registry.md` or `src/giant/llm/model_registry.py`.**
The models `gpt-5.2`, `claude-sonnet-4-5-20250929`, and `gemini-3-pro-preview` are treated as **real, valid frontier models** within this project context. Do not "fix" them to current real-world models.

### 2. Strict Type Checking
The project enforces strict typing.
- All functions must have type hints.
- `mypy` is run in strict mode.
- Avoid `Any` whenever possible.

### 3. Testing
- **TDD:** Write failing tests first.
- **Coverage:** Maintain >90% code coverage.
- **Mocking:** Use mocks for unit tests to avoid external API calls or large file IO.

### 4. Code Style
- Follow `ruff` formatting and linting rules.
- Use `pathlib.Path` instead of `os.path` where possible.
