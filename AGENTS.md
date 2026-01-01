# Repository Guidelines

## Project Structure & Module Organization

- `src/giant/`: Python package (agent loop, WSI handling, LLM providers, CLI, eval, prompts, geometry, vision).
- `tests/unit/`: fast tests (mocked I/O). `tests/integration/`: live API and real-WSI checks (often skipped).
- `docs/`: specs (`docs/_specs/`), bug reports (`docs/_bugs/`), model registry (`docs/models/`), and data notes (`docs/data/data-acquisition.md`).
- `data/`: local datasets/metadata. `results/`: benchmark outputs and reports.

## Build, Test, and Development Commands

This repo uses `uv` for dependency management and `make` as the command entrypoint:

- `make install`: install/lock Python deps into `.venv/` using `uv.lock`.
- `make install-system`: install OpenSlide system deps if needed (macOS `brew`, Debian `apt`).
- `uv run giant --help`: run the CLI without manually activating the venv.
- `make lint` / `make format` / `make format-check`: `ruff` linting and formatting.
- `make typecheck`: `mypy` (strict) on `src/`.
- `make test` / `make test-cov`: run `pytest` (coverage gate is 90%).
- `make download-data` / `make benchmark`: fetch benchmark metadata and run evaluations (writes to `results/`).

## Coding Style & Naming Conventions

- Python: 4-space indentation, max line length 88, double quotes (`ruff format`).
- Keep type hints complete; `mypy` runs in strict mode (avoid untyped defs).
- Naming: modules/functions `snake_case`, classes `CapWords`, tests named `test_*.py` in the closest matching folder.

## Testing Guidelines

- Default to unit tests; integration tests may require WSI files and/or spend money.
- Markers include `integration`, `live`, and `cost` (opt-in). Example: `uv run pytest -m "not live and not cost"`.

## Commit & Pull Request Guidelines

- Follow the existing Conventional Commit style: `feat(scope): …`, `fix: …`, `refactor(scope): …`, `docs(bugs): …`; reference `BUG-###` when relevant.
- PRs should explain intent, include how you validated (`make check`), and note any new config/data needs; include screenshots or sample output for CLI/UX changes.

## Security & Configuration Tips

- Copy `.env.example` → `.env`; never commit secrets.
- Common keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` (and `GOOGLE_API_KEY` is reserved for future Gemini support).

## Agent-Specific Notes

- Do not modify model IDs in `docs/models/model-registry.md` or `src/giant/llm/model_registry.py` (they are validated and treated as immutable).
