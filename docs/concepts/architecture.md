# Architecture

GIANT follows a modular architecture with clear separation of concerns. This page describes the major components and how they interact.

## High-Level Design

```
┌─────────────────────────────────────────────────────────────────┐
│                           CLI Layer                              │
│                    giant run / giant benchmark                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Agent Layer                              │
│  ┌────────────┐ ┌───────────────┐ ┌────────────┐               │
│  │GIANTAgent  │ │ContextManager │ │ Trajectory │               │
│  │(runner.py) │ │  (context.py) │ │(trajectory)│               │
│  └────────────┘ └───────────────┘ └────────────┘               │
└─────────────────────────────────────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           ▼                  ▼                  ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│   WSI Layer      │ │   LLM Layer      │ │  Prompt Layer    │
│ ┌──────────────┐ │ │ ┌──────────────┐ │ │ ┌──────────────┐ │
│ │ WSIReader    │ │ │ │ LLMProvider  │ │ │ │PromptBuilder │ │
│ │ CropEngine   │ │ │ │ OpenAI       │ │ │ │ Templates    │ │
│ │ LevelSelector│ │ │ │ Anthropic    │ │ │ └──────────────┘ │
│ └──────────────┘ │ │ └──────────────┘ │ └──────────────────┘
│ ┌──────────────┐ │ │ ┌──────────────┐ │
│ │ OverlayGen   │ │ │ │ModelRegistry │ │
│ │ AxisGuides   │ │ │ │ Pricing      │ │
│ └──────────────┘ │ │ └──────────────┘ │
└──────────────────┘ └──────────────────┘
```

## Module Overview

### Agent Layer (`src/giant/agent/`)

The orchestration layer that implements the navigation algorithm.

| File | Class | Responsibility |
|------|-------|----------------|
| `runner.py` | `GIANTAgent` | Main agent loop, error handling, retry logic |
| `context.py` | `ContextManager` | Multi-turn conversation state |
| `trajectory.py` | `Trajectory` | Step recording for evaluation |

### WSI Layer (`src/giant/wsi/`, `src/giant/core/`)

Handles whole-slide image I/O and processing.

| File | Class | Responsibility |
|------|-------|----------------|
| `reader.py` | `WSIReader` | OpenSlide wrapper, thumbnail generation |
| `crop_engine.py` | `CropEngine` | Region extraction, level selection |
| `level_selector.py` | `LevelSelector` | Optimal pyramid level algorithm |

### Geometry Layer (`src/giant/geometry/`)

Coordinate systems and visual overlays.

| File | Class | Responsibility |
|------|-------|----------------|
| `primitives.py` | `Region`, `Point`, `Size` | Value objects |
| `overlay.py` | `AxisGuideGenerator` | Axis labels on thumbnails |
| `validators.py` | `GeometryValidator` | Bounds checking |

### LLM Layer (`src/giant/llm/`)

Abstracts LLM API interactions.

| File | Class | Responsibility |
|------|-------|----------------|
| `protocol.py` | `LLMProvider` | Protocol interface |
| `openai_client.py` | `OpenAIProvider` | OpenAI Responses API |
| `anthropic_client.py` | `AnthropicProvider` | Anthropic Messages API |
| `model_registry.py` | - | Approved models, validation |
| `pricing.py` | - | Cost calculation |

### Prompt Layer (`src/giant/prompts/`)

Prompt engineering and templates.

| File | Class | Responsibility |
|------|-------|----------------|
| `builder.py` | `PromptBuilder` | Assembles prompts per step |
| `templates.py` | - | System/user prompt templates |

### Evaluation Layer (`src/giant/eval/`)

Benchmark running and metrics.

| File | Class | Responsibility |
|------|-------|----------------|
| `runner.py` | `BenchmarkRunner` | Orchestrates benchmark runs |
| `metrics.py` | - | Accuracy, balanced accuracy |
| `answer_extraction.py` | - | Parse model answers |
| `resumable.py` | - | Checkpoint/resume logic |

### CLI Layer (`src/giant/cli/`)

Command-line interface.

| File | Responsibility |
|------|----------------|
| `main.py` | Typer app, command definitions |
| `runners.py` | CLI command implementations |
| `visualizer.py` | HTML trajectory viewer |

## Data Flow

### Single Inference

```
1. CLI receives: wsi_path, question, provider, model
                    │
2. Create LLMProvider(model)
                    │
3. Create GIANTAgent(wsi_path, question, provider)
                    │
4. agent.run():
   │
   ├─► WSIReader opens slide
   │
   ├─► Generate thumbnail + axis guides
   │
   └─► Navigation loop:
       │
       ├─► ContextManager builds messages
       │
       ├─► LLMProvider.generate_response()
       │
       ├─► Parse action (crop or answer)
       │
       ├─► If crop: CropEngine extracts region
       │             ContextManager.add_turn()
       │             Continue loop
       │
       └─► If answer: Return RunResult
                    │
5. Return answer, cost, trajectory
```

### Benchmark Run

```
1. BenchmarkRunner loads MultiPathQA.csv
                    │
2. Filter by benchmark_name
                    │
3. For each item (with concurrency):
   │
   ├─► Resolve WSI path
   │
   ├─► Create GIANTAgent
   │
   ├─► Run agent, record result
   │
   └─► Checkpoint progress
                    │
4. Calculate metrics (balanced accuracy, etc.)
                    │
5. Save results JSON
```

## Design Patterns

### Protocol Pattern (LLMProvider)

All LLM providers implement the `LLMProvider` protocol:

```python
class LLMProvider(Protocol):
    async def generate_response(self, messages: list[Message]) -> LLMResponse: ...
    def get_model_name(self) -> str: ...
    def get_target_size(self) -> int: ...
```

This allows swapping providers without changing agent code.

### Factory Pattern

Providers are created via factory function:

```python
from giant.llm import create_provider
provider = create_provider("openai", model="gpt-5.2")
```

### Value Objects

Geometry uses immutable value objects:

```python
from giant.geometry import Region, Point, Size

region = Region(x=1000, y=2000, width=500, height=500)
```

## Configuration

Configuration flows from:

1. **CLI arguments** - User-provided options
2. **AgentConfig** - Agent behavior settings
3. **Environment** - API keys from `.env`
4. **Model Registry** - Approved models

See [Configuration Reference](../reference/configuration.md) for details.

## Next Steps

- [Algorithm](algorithm.md) - Navigation algorithm details
- [LLM Integration](llm-integration.md) - Provider implementations
- [Project Structure](../reference/project-structure.md) - File organization
