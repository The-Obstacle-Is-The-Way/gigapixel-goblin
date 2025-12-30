# GIANT

**Gigapixel Image Agent for Navigating Tissue**

GIANT is an agentic system that uses large language models to autonomously navigate whole-slide images (WSIs) for pathology analysis. The agent iteratively examines regions of a gigapixel image, zooming in on areas of interest until it can answer a question about the slide.

## Key Features

- **Autonomous Navigation** - LLM decides where to look next based on visual content
- **Multi-Scale Analysis** - Examines both tissue architecture and cellular detail
- **Provider Agnostic** - Supports OpenAI and Anthropic providers (Gemini planned)
- **Benchmark Evaluation** - Reproduce results on MultiPathQA (GTEx, TCGA, PANDA)
- **Trajectory Visualization** - Interactive viewer for agent reasoning

## Quick Start

```bash
# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate

# Configure API key
export OPENAI_API_KEY=sk-...

# Run on a single WSI
giant run /path/to/slide.svs -q "What tissue is this?"

# Run benchmark
giant benchmark gtex --provider openai
```

## How It Works

```
┌─────────────────────────────────────────────┐
│  1. Load WSI + Generate Thumbnail           │
│     ┌─────────────────┐                     │
│     │ ███████████████ │ + Axis Guides       │
│     │ █   Tissue    █ │                     │
│     │ ███████████████ │                     │
│     └─────────────────┘                     │
├─────────────────────────────────────────────┤
│  2. LLM Analyzes + Selects Region           │
│     "I see suspicious area at (45K, 32K)    │
│      Let me zoom in for cellular detail..." │
├─────────────────────────────────────────────┤
│  3. Extract High-Res Crop                   │
│     ┌───────┐                               │
│     │░░░░░░░│ 1000x1000 @ high resolution   │
│     │░░░░░░░│                               │
│     └───────┘                               │
├─────────────────────────────────────────────┤
│  4. Repeat Until Answer                     │
│     "Based on cellular morphology,          │
│      this is adenocarcinoma."               │
└─────────────────────────────────────────────┘
```

## Benchmark Results

| Benchmark | Task | Our Result | Paper (GIANT x1) | Paper (GIANT x5) | Thumbnail Baseline |
|-----------|------|------------|------------------|------------------|--------------------|
| GTEx | Organ Classification (20-way) | **70.3%** | 53.7% ± 3.4% | 60.7% ± 3.2% | 36.5% ± 3.4% |
| TCGA | Cancer Diagnosis (30-way) | **26.2%** | 32.3% ± 3.5% | 29.3% ± 3.3% | 9.2% ± 1.9% |
| PANDA | Prostate Grading (6-way) | **20.3%** (rescored) | 23.2% ± 2.3% | 25.4% ± 2.0% | 12.2% ± 2.2% |

- **GTEx (70.3%)**: Exceeds the paper's GPT-5 + GIANT x1 (53.7%) and x5 (60.7%) results.
- **TCGA (26.2%)**: Below the paper's GIANT x1 (32.3%), but above paper thumbnail (9.2%) and patch (12.8%) baselines.
- **PANDA (20.3%)**: Improved via extraction + parsing fixes; rescored from saved artifacts without new LLM calls.

## Supported Models

| Provider | Model | Status |
|----------|-------|--------|
| OpenAI | `gpt-5.2` | Default |
| Anthropic | `claude-sonnet-4-5-20250929` | Supported |
| Google | `gemini-3-pro-preview` | Planned (not yet implemented) |

## Documentation

### Getting Started

- [Installation](getting-started/installation.md) - Set up your development environment
- [Quickstart](getting-started/quickstart.md) - Run your first inference
- [First Benchmark](getting-started/first-benchmark.md) - Reproduce paper results

### Understanding GIANT

- [What is GIANT?](concepts/overview.md) - High-level overview
- [Architecture](concepts/architecture.md) - System design
- [Navigation Algorithm](concepts/algorithm.md) - Core algorithm explanation
- [LLM Integration](concepts/llm-integration.md) - Provider implementations

### How-To Guides

- [Running Inference](guides/running-inference.md) - Single WSI analysis
- [Running Benchmarks](guides/running-benchmarks.md) - Full benchmark evaluation
- [Configuring Providers](guides/configuring-providers.md) - API key setup
- [Visualizing Trajectories](guides/visualizing-trajectories.md) - Inspect agent behavior

### Reference

- [CLI Reference](reference/cli.md) - Command-line options
- [Configuration](reference/configuration.md) - All configuration options
- [Project Structure](reference/project-structure.md) - Codebase organization
- [Model Registry](models/model-registry.md) - Approved models

### Development

- [Contributing](development/contributing.md) - How to contribute
- [Testing](development/testing.md) - Testing practices
- [Specifications](specs/README.md) - Implementation specs (Spec-01 to Spec-12)

## Data Requirements

The MultiPathQA benchmark requires **862 unique WSI files** (~500+ GiB):

- **TCGA**: 474 `.svs` files (~472 GiB)
- **GTEx**: 191 `.tiff` files
- **PANDA**: 197 `.tiff` files

See [Data Acquisition](data-acquisition.md) for download instructions.

## Links

- [GitHub Repository](https://github.com/The-Obstacle-Is-The-Way/gigapixel-goblin)
- [GIANT Paper](https://arxiv.org/abs/2511.19652)
- [MultiPathQA Dataset](https://huggingface.co/datasets/tbuckley/MultiPathQA)
