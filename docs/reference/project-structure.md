# Project Structure

This page documents the organization of the GIANT codebase.

## Repository Layout

```
gigapixel-goblin/
├── src/giant/              # Main source code
├── tests/                  # Test suite
├── docs/                   # Documentation (MkDocs)
├── data/                   # Data files (not in git)
├── results/                # Benchmark results (not in git)
├── scripts/                # Utility scripts
├── pyproject.toml          # Project configuration
├── mkdocs.yml              # Documentation config
├── CLAUDE.md               # AI assistant instructions
└── README.md               # Project readme
```

## Source Code (`src/giant/`)

### Module Overview

```
src/giant/
├── __init__.py             # Package root, version
├── config.py               # Global configuration
│
├── agent/                  # Agent orchestration
│   ├── __init__.py
│   ├── runner.py           # GIANTAgent class
│   ├── context.py          # ContextManager
│   └── trajectory.py       # Trajectory recording
│
├── llm/                    # LLM abstraction
│   ├── __init__.py         # create_provider factory
│   ├── protocol.py         # LLMProvider Protocol
│   ├── openai_client.py    # OpenAI implementation
│   ├── anthropic_client.py # Anthropic implementation
│   ├── converters.py       # Message format conversion
│   ├── model_registry.py   # Approved models
│   ├── pricing.py          # Cost calculation
│   ├── schemas.py          # JSON schemas
│   └── circuit_breaker.py  # Failure protection
│
├── wsi/                    # WSI I/O
│   ├── __init__.py
│   ├── reader.py           # WSIReader class
│   ├── types.py            # WSI metadata types
│   └── exceptions.py       # WSI errors
│
├── core/                   # Core processing
│   ├── __init__.py
│   ├── crop_engine.py      # CropEngine class
│   ├── level_selector.py   # Pyramid level selection
│   └── baselines.py        # Thumbnail/patch baselines
│
├── geometry/               # Coordinates & overlays
│   ├── __init__.py
│   ├── primitives.py       # Region, Point, Size
│   ├── overlay.py          # Axis guide generation
│   ├── transforms.py       # Coordinate transforms
│   └── validators.py       # Bounds validation
│
├── prompts/                # Prompt engineering
│   ├── __init__.py
│   ├── builder.py          # PromptBuilder class
│   └── templates.py        # Prompt templates
│
├── eval/                   # Evaluation framework
│   ├── __init__.py
│   ├── runner.py           # BenchmarkRunner class
│   ├── metrics.py          # Accuracy calculations
│   ├── answer_extraction.py# Parse model answers
│   ├── wsi_resolver.py     # Resolve WSI paths
│   └── resumable.py        # Checkpoint/resume
│
├── vision/                 # Computer vision
│   ├── __init__.py
│   ├── segmentation.py     # Tissue segmentation
│   ├── sampler.py          # Patch sampling
│   ├── aggregation.py      # Feature aggregation
│   └── constants.py        # Vision constants
│
├── data/                   # Data utilities
│   ├── __init__.py
│   ├── download.py         # Dataset download
│   ├── schemas.py          # Data schemas
│   └── tcga.py             # TCGA-specific helpers
│
├── cli/                    # Command-line interface
│   ├── __init__.py
│   ├── main.py             # Typer app
│   ├── runners.py          # Command implementations
│   └── visualizer.py       # Trajectory visualization
│
└── utils/                  # Utilities
    ├── __init__.py
    └── logging.py          # Logging configuration
```

## Key Classes

### Agent Layer

| Class | File | Purpose |
|-------|------|---------|
| `GIANTAgent` | `agent/runner.py` | Main navigation loop |
| `ContextManager` | `agent/context.py` | Conversation state |
| `Trajectory` | `agent/trajectory.py` | Step recording |

### LLM Layer

| Class | File | Purpose |
|-------|------|---------|
| `LLMProvider` | `llm/protocol.py` | Provider interface |
| `OpenAIProvider` | `llm/openai_client.py` | OpenAI Responses API |
| `AnthropicProvider` | `llm/anthropic_client.py` | Anthropic Messages API |
| `Message` | `llm/protocol.py` | Message format |
| `StepResponse` | `llm/protocol.py` | LLM output format |

### WSI Layer

| Class | File | Purpose |
|-------|------|---------|
| `WSIReader` | `wsi/reader.py` | OpenSlide wrapper |
| `CropEngine` | `core/crop_engine.py` | Region extraction |
| `PyramidLevelSelector` | `core/level_selector.py` | Pyramid level selection |

### Geometry Layer

| Class | File | Purpose |
|-------|------|---------|
| `Region` | `geometry/primitives.py` | Bounding box |
| `Point` | `geometry/primitives.py` | Coordinate point |
| `Size` | `geometry/primitives.py` | Dimensions |
| `AxisGuideGenerator` | `geometry/overlay.py` | Axis labels |

### Evaluation Layer

| Class | File | Purpose |
|-------|------|---------|
| `BenchmarkRunner` | `eval/runner.py` | Benchmark orchestration |
| `EvaluationConfig` | `eval/runner.py` | Run configuration |

## Tests (`tests/`)

```
tests/
├── conftest.py             # Shared fixtures
├── unit/                   # Unit tests (fast, mocked)
│   ├── agent/
│   ├── cli/
│   ├── core/
│   ├── data/
│   ├── eval/
│   ├── geometry/
│   ├── llm/
│   ├── prompts/
│   ├── vision/
│   └── wsi/
└── integration/            # Integration tests (real I/O)
    ├── cli/
    ├── llm/
    └── wsi/
```

### Test Markers

| Marker | Description |
|--------|-------------|
| `@pytest.mark.cost` | Requires live API (costs money) |
| `@pytest.mark.integration` | Requires real WSI files |
| `@pytest.mark.live` | Requires live external service |

## Documentation (`docs/`)

```
docs/
├── index.md                # Home page
├── getting-started/        # Tutorials
├── concepts/               # Explanations
├── guides/                 # How-to guides
├── reference/              # Reference docs
├── development/            # Contributing
├── specs/                  # Implementation specs
├── models/                 # Model registry
├── prompts/                # Prompt design
├── results/                # Benchmark results
├── validation/             # Validation reports
├── bugs/                   # Bug tracking
├── archive/                # Archived bugs
├── brainstorming/          # Research notes
└── data-acquisition.md     # Data download guide
```

## Data (`data/`)

```
data/
├── multipathqa/
│   └── MultiPathQA.csv     # Benchmark metadata
├── wsi/
│   ├── tcga/               # TCGA slides
│   ├── gtex/               # GTEx slides
│   ├── panda/              # PANDA slides
│   ├── tcga_files.txt      # TCGA file list
│   ├── gtex_files.txt      # GTEx file list
│   └── panda_files.txt     # PANDA file list
└── test/                   # Test data
```

## Results (`results/`)

```
results/
├── *_results.json          # Full benchmark results
├── checkpoints/
│   └── *.checkpoint.json   # Resume state
└── trajectories/
    └── *.json              # Per-item trajectories
```

## Configuration Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Project metadata, dependencies |
| `mkdocs.yml` | Documentation site config |
| `.env` | Environment variables (not in git) |
| `.gitignore` | Git ignore patterns |
| `CLAUDE.md` | AI assistant instructions |
| `GEMINI.md` | AI assistant instructions |

## Import Patterns

### Public API

```python
# Agent
from giant.agent import GIANTAgent, AgentConfig

# LLM
from giant.llm import create_provider, LLMProvider

# Geometry
from giant.geometry import Region, Point, Size

# WSI
from giant.wsi import WSIReader

# Core
from giant.core import CropEngine

# Evaluation
from giant.eval import BenchmarkRunner, EvaluationConfig
```

## See Also

- [Architecture](../concepts/architecture.md)
- [Contributing](../development/contributing.md)
- [Testing](../development/testing.md)
