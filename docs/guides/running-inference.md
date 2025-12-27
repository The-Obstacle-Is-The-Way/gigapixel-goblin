# Running Inference

This guide covers running GIANT on single whole-slide images.

## Basic Usage

```bash
giant run <wsi_path> -q "<question>"
```

### Example

```bash
giant run data/wsi/tcga/TCGA-02-0266-01Z-00-DX1.svs \
    -q "What type of cancer is shown in this slide?"
```

## Command Options

### Required Arguments

| Argument | Description |
|----------|-------------|
| `WSI_PATH` | Path to the WSI file (`.svs`, `.tiff`, `.ndpi`) |
| `-q, --question` | Question to answer about the slide |

### Provider Options

| Option | Default | Description |
|--------|---------|-------------|
| `-p, --provider` | `openai` | LLM provider (`openai`, `anthropic`) |
| `--model` | `gpt-5.2` | Model ID (see Model Registry) |

```bash
# Use Anthropic
giant run slide.svs -q "Question?" --provider anthropic

# Specify model explicitly
giant run slide.svs -q "Question?" --provider openai --model gpt-5.2
```

### Navigation Options

| Option | Default | Description |
|--------|---------|-------------|
| `-T, --max-steps` | `20` | Maximum navigation steps |
| `--budget-usd` | `0` (disabled) | Cost limit in USD |
| `-m, --mode` | `giant` | Evaluation mode |

```bash
# Limit to 5 navigation steps
giant run slide.svs -q "Question?" --max-steps 5

# Set cost budget ($0.50 max)
giant run slide.svs -q "Question?" --budget-usd 0.50
```

### Output Options

| Option | Default | Description |
|--------|---------|-------------|
| `-o, --output` | None | Save trajectory to JSON |
| `--json` | False | Output as JSON (for scripting) |
| `-v, --verbose` | 0 | Increase verbosity (`-v`, `-vv`, `-vvv`) |

```bash
# Save trajectory for visualization
giant run slide.svs -q "Question?" -o trajectory.json

# JSON output for scripting
giant run slide.svs -q "Question?" --json | jq '.answer'

# Verbose logging
giant run slide.svs -q "Question?" -vv
```

### Multiple Runs

| Option | Default | Description |
|--------|---------|-------------|
| `-r, --runs` | `1` | Number of runs for majority voting |

```bash
# Run 3 times, take majority vote
giant run slide.svs -q "Question?" --runs 3
```

With `--runs > 1`, output includes:
- `answer`: Most common answer
- `agreement`: Fraction of runs that agreed

## Evaluation Modes

GIANT supports three evaluation modes:

| Mode | Description |
|------|-------------|
| `giant` | Full agentic navigation (default) |
| `thumbnail` | Single thumbnail, no cropping |
| `patch` | Random patch sampling (CLAM-style) |

```bash
# Compare methods
giant run slide.svs -q "Question?" --mode giant
giant run slide.svs -q "Question?" --mode thumbnail
giant run slide.svs -q "Question?" --mode patch
```

## Output Format

### Standard Output

```
Answer: This slide shows adenocarcinoma of the lung...
Cost: $0.0432
Turns: 4
```

### JSON Output (`--json`)

```json
{
  "success": true,
  "answer": "This slide shows adenocarcinoma of the lung...",
  "total_cost": 0.0432,
  "agreement": 1.0,
  "turns": 4
}
```

### Trajectory File (`--output`)

```json
{
  "wsi_path": "/path/to/slide.svs",
  "question": "What type of cancer...",
  "turns": [
    {
      "step_index": 0,
      "image_base64": "...",
      "response": {
        "reasoning": "I see a tissue sample with...",
        "action": {"action_type": "crop", "x": 45000, ...}
      },
      "region": {"x": 45000, "y": 32000, ...}
    },
    ...
  ],
  "answer": "This slide shows adenocarcinoma...",
  "success": true,
  "total_cost": 0.0432
}
```

## Error Handling

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Failure (error message in stderr) |

### Common Errors

**WSI file not found:**
```
Error: Path 'slide.svs' does not exist.
```

**OpenSlide can't read file:**
```
Error: openslide.OpenSlideError: Cannot open ...
```

**API key not configured:**
```
Error: OPENAI_API_KEY not set
```

**Budget exceeded:**
```
Error: Budget exceeded ($0.50 >= $0.50)
```

## Examples

### Cancer Diagnosis

```bash
giant run data/wsi/tcga/TCGA-02-0266-01Z-00-DX1.svs \
    -q "What type of cancer is present in this slide? Options: Lung Adenocarcinoma, Breast Invasive Carcinoma, Kidney Renal Clear Cell Carcinoma"
```

### Tissue Classification

```bash
giant run data/wsi/gtex/GTEX-OIZH-0626.tiff \
    -q "What organ is this tissue from? Options: Heart, Lung, Liver, Kidney, Brain"
```

### Grading

```bash
giant run data/wsi/panda/abc123.tiff \
    -q "What is the ISUP grade group for this prostate biopsy? Options: 0, 1, 2, 3, 4, 5"
```

### Quick Test (Cost-Limited)

```bash
giant run slide.svs -q "What tissue is this?" \
    --max-steps 3 \
    --budget-usd 0.10 \
    -v
```

## Visualizing Results

After running with `--output`:

```bash
giant visualize trajectory.json --open
```

See [Visualizing Trajectories](visualizing-trajectories.md) for details.

## Next Steps

- [Running Benchmarks](running-benchmarks.md) - Batch evaluation
- [Configuring Providers](configuring-providers.md) - API setup
- [CLI Reference](../reference/cli.md) - All options
