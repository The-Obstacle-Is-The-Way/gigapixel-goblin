# Quickstart

Run your first GIANT inference on a whole-slide image.

## Prerequisites

- [Installation](installation.md) completed
- OpenAI or Anthropic API key configured in `.env`
- A WSI file (`.svs`, `.tiff`, or `.ndpi` format)

## Download a Test Slide

For testing, download a small WSI from OpenSlide's test data:

```bash
mkdir -p data/test
curl -L -o data/test/CMU-1-Small-Region.svs \
    https://openslide.cs.cmu.edu/download/openslide-testdata/Aperio/CMU-1-Small-Region.svs
```

## Run Inference

### Basic Usage

```bash
# Activate environment and load API keys
source .venv/bin/activate
source .env

# Run GIANT on a WSI with a question
giant run data/test/CMU-1-Small-Region.svs \
    -q "What type of tissue is shown in this slide?"
```

### Expected Output

```
Answer: This slide shows squamous epithelial tissue...
Cost: $0.0234
Turns: 3
```

## CLI Options

```bash
# Use Anthropic instead of OpenAI
giant run slide.svs -q "Question?" --provider anthropic

# Limit navigation steps
giant run slide.svs -q "Question?" --max-steps 5

# Set a cost budget (USD)
giant run slide.svs -q "Question?" --budget-usd 0.10

# Save the navigation trajectory
giant run slide.svs -q "Question?" --output trajectory.json

# Multiple runs with majority voting
giant run slide.svs -q "Question?" --runs 3

# JSON output for scripting
giant run slide.svs -q "Question?" --json
```

## Understanding the Output

GIANT returns:

| Field | Description |
|-------|-------------|
| `answer` | The model's response to your question |
| `cost` | Total API cost in USD |
| `turns` | Number of navigation steps taken |
| `agreement` | (with `--runs > 1`) Fraction of runs that agreed |

## Visualize Navigation

After running with `--output`, visualize the agent's trajectory:

```bash
giant visualize trajectory.json --open
```

This opens an interactive HTML viewer showing:

- Initial thumbnail with axis guides
- Each cropped region the agent examined
- The agent's reasoning at each step
- Final answer

## Next Steps

- [First Benchmark](first-benchmark.md) - Run on real benchmark data
- [Algorithm Explanation](../concepts/algorithm.md) - Understand how GIANT navigates
- [CLI Reference](../reference/cli.md) - All command options
