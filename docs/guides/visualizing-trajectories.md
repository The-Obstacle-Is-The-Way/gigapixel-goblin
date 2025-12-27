# Visualizing Trajectories

This guide covers using GIANT's trajectory visualization tools.

## Overview

After running inference with `--output`, you can visualize the agent's navigation:

```bash
# Run with trajectory output
giant run slide.svs -q "Question?" -o trajectory.json

# Visualize
giant visualize trajectory.json
```

## Basic Usage

```bash
giant visualize <trajectory_path> [options]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `-o, --output` | Auto-generated | Output HTML file path |
| `--open/--no-open` | `--open` | Open in browser |
| `-v, --verbose` | 0 | Verbosity level |
| `--json` | False | JSON output |

### Examples

```bash
# Open in browser (default)
giant visualize trajectory.json

# Save without opening
giant visualize trajectory.json --no-open -o my_viz.html

# Specify output path
giant visualize trajectory.json -o results/viz/run1.html
```

## Visualization Features

### Thumbnail View

The initial view shows the full slide thumbnail with:

- **Axis guides** - Red lines with coordinate labels
- **Crop overlays** - Rectangles showing examined regions
- **Region numbers** - Step index for each crop

### Step-by-Step View

Each navigation step displays:

| Element | Description |
|---------|-------------|
| Image | The cropped region shown to the model |
| Reasoning | Model's chain-of-thought explanation |
| Action | Crop coordinates or final answer |
| Metadata | Step number, cost, tokens |

### Final Answer

The visualization highlights:

- Total navigation steps
- Final answer text
- Total cost
- Accuracy (if ground truth available)

## Trajectory File Format

The trajectory JSON contains:

```json
{
  "wsi_path": "/path/to/slide.svs",
  "question": "What type of cancer is shown?",
  "slide_width": 100000,
  "slide_height": 80000,
  "thumbnail_base64": "...",
  "turns": [
    {
      "step_index": 0,
      "image_base64": "...",
      "response": {
        "reasoning": "I observe a tissue section with...",
        "action": {
          "action_type": "crop",
          "x": 45000,
          "y": 32000,
          "width": 10000,
          "height": 10000
        }
      },
      "region": {
        "x": 45000,
        "y": 32000,
        "width": 10000,
        "height": 10000
      }
    },
    {
      "step_index": 1,
      "image_base64": "...",
      "response": {
        "reasoning": "At higher magnification, I can see...",
        "action": {
          "action_type": "answer",
          "answer_text": "This is adenocarcinoma."
        }
      },
      "region": null
    }
  ],
  "answer": "This is adenocarcinoma.",
  "success": true,
  "total_cost": 0.0432,
  "mode": "giant",
  "provider": "openai",
  "model": "gpt-5.2"
}
```

## Batch Visualization

For benchmark runs, trajectories are saved per-item:

```
results/trajectories/
├── GTEX-OIZH-0626_run0.json
├── GTEX-ABCD-1234_run0.json
└── ...
```

Visualize individual items:

```bash
giant visualize results/trajectories/GTEX-OIZH-0626_run0.json
```

### Batch Script

```bash
# Visualize all trajectories
for f in results/trajectories/*.json; do
    giant visualize "$f" --no-open -o "${f%.json}.html"
done
```

## Programmatic Access

```python
from giant.cli.visualizer import create_trajectory_html
from pathlib import Path

html_path = create_trajectory_html(
    trajectory_path=Path("trajectory.json"),
    output_path=Path("output.html"),
    open_browser=False,
)
print(f"Saved to: {html_path}")
```

## Understanding the Visualization

### Successful Navigation

A good trajectory shows:

1. **Purposeful exploration** - Model zooms into relevant regions
2. **Progressive refinement** - Each step adds information
3. **Clear reasoning** - Explanations reference visual features
4. **Confident answer** - Final answer with supporting evidence

### Common Patterns

| Pattern | Meaning |
|---------|---------|
| Few steps, quick answer | Obvious case or thumbnail sufficient |
| Many steps, gradual zoom | Complex case requiring detail |
| Multiple regions | Model sampling different areas |
| Error retries | Invalid coordinates corrected |

### Failure Modes

| Pattern | Issue |
|---------|-------|
| Random exploration | Model not understanding task |
| Repeated same region | Model stuck in loop |
| No answer at limit | Insufficient evidence gathered |
| Invalid coordinates | Model confused by axis guides |

## Troubleshooting

### "Trajectory file not found"

Ensure you ran inference with `--output`:

```bash
giant run slide.svs -q "?" -o trajectory.json
```

### "Missing images in visualization"

The trajectory must include `thumbnail_base64` and per-turn `image_base64`. Older trajectories may lack these fields.

### "Browser doesn't open"

Use explicit browser:

```bash
giant visualize traj.json --no-open -o viz.html
open viz.html  # macOS
xdg-open viz.html  # Linux
```

## Next Steps

- [Running Inference](running-inference.md) - Generate trajectories
- [Algorithm](../concepts/algorithm.md) - Navigation algorithm
- [Benchmark Results](../results/benchmark-results.md) - Example trajectories
