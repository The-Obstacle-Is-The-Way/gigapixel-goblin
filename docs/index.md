# GIANT

**Gigapixel Image Agent for Navigating Tissue**

GIANT is an agentic system that uses LLMs to autonomously navigate whole-slide images (WSI) for pathology analysis. The agent iteratively crops regions based on LLM decisions until it can answer a question about the slide.

## Quick Start

```bash
# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate

# Run on a single WSI
giant run /path/to/slide.svs -q "What tissue is this?"

# Run benchmark
giant benchmark gtex --provider openai --model gpt-5.2
```

## Architecture

The core algorithm (from the GIANT paper):

1. `GIANTAgent` opens WSI via `WSIReader` and generates thumbnail with axis guides
2. LLM examines thumbnail and outputs structured JSON: `{reasoning, action}`
3. If `action.type == "crop"`: `CropEngine` extracts region, loop continues
4. If `action.type == "answer"`: navigation ends with final answer
5. `ContextManager` maintains multi-turn conversation history
6. `Trajectory` records all steps for evaluation and visualization

## Documentation

- **[Data Acquisition](data-acquisition.md)**: How to download WSI files for benchmarking
- **[Specifications](specs/README.md)**: Detailed implementation specs (Spec-01 through Spec-12)
- **[Model Registry](models/model-registry.md)**: Approved LLM models and pricing
- **[Benchmark Results](results/benchmark-results.md)**: MultiPathQA benchmark performance

## Supported Models

| Provider | Model | Status |
|----------|-------|--------|
| OpenAI | `gpt-5.2` | Default |
| Anthropic | `claude-sonnet-4-5-20250929` | Supported |
| Google | `gemini-3-pro-preview` | Supported |

## Benchmarks

| Benchmark | Task | Our Result | Paper (GIANT x1) |
|-----------|------|------------|------------------|
| GTEx | Organ Classification (20-way) | **67.6%** | 60.7% |
| TCGA | Cancer Diagnosis (30-way) | In Progress | 32.3% |
| PANDA | Prostate Grading (6-way) | Pending | 25.4% |

## Links

- [GitHub Repository](https://github.com/The-Obstacle-Is-The-Way/gigapixel-goblin)
- [GIANT Paper](https://arxiv.org/abs/2511.19652)
- [MultiPathQA Dataset](https://huggingface.co/datasets/tbuckley/MultiPathQA)
