# CLI Reference

Complete reference for the GIANT command-line interface.

## Synopsis

```bash
giant <command> [options]
```

## Global Commands

### `giant version`

Show version information.

```bash
giant version
giant version --json
```

| Option | Description |
|--------|-------------|
| `--json` | Output as JSON |

---

## `giant run`

Run GIANT on a single whole-slide image.

```bash
giant run <wsi_path> -q <question> [options]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `WSI_PATH` | Yes | Path to WSI file (`.svs`, `.tiff`, `.ndpi`) |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `-q, --question` | Required | Question to answer about the slide |
| `-m, --mode` | `giant` | Evaluation mode (`giant`, `thumbnail`, `patch`) |
| `-p, --provider` | `openai` | LLM provider (`openai`, `anthropic`) |
| `--model` | `gpt-5.2` | Model ID (see model-registry.md) |
| `-T, --max-steps` | `20` | Maximum navigation steps |
| `--strict-font-check/--no-strict-font-check` | `--no-strict-font-check` | Fail if TrueType fonts unavailable |
| `-r, --runs` | `1` | Number of runs for majority voting |
| `--budget-usd` | `0` (disabled) | Cost limit in USD |
| `-o, --output` | None | Save trajectory to JSON file |
| `-v, --verbose` | 0 | Verbosity level (`-v`, `-vv`, `-vvv`) |
| `--json` | False | Output as JSON |

### Examples

```bash
# Basic usage
giant run slide.svs -q "What tissue is this?"

# Use Anthropic with cost limit
giant run slide.svs -q "Question?" --provider anthropic --budget-usd 0.50

# Multiple runs with trajectory output
giant run slide.svs -q "Question?" --runs 3 -o trajectory.json -v
```

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Failure |

---

## `giant benchmark`

Run the full benchmark suite on a dataset.

```bash
giant benchmark <dataset> [options]
```

### Arguments

| Argument | Values | Description |
|----------|--------|-------------|
| `DATASET` | `tcga`, `panda`, `gtex`, `tcga_expert_vqa`, `tcga_slidebench` | Dataset name |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--csv-path` | `data/multipathqa/MultiPathQA.csv` | Path to benchmark CSV |
| `--wsi-root` | `data/wsi` | Root directory for WSI files |
| `-o, --output-dir` | `results` | Output directory for results |
| `-m, --mode` | `giant` | Evaluation mode |
| `-p, --provider` | `openai` | LLM provider |
| `--model` | `gpt-5.2` | Model ID |
| `-T, --max-steps` | `20` | Max steps per item |
| `--strict-font-check/--no-strict-font-check` | `--no-strict-font-check` | Font check |
| `-r, --runs` | `1` | Runs per item |
| `-c, --concurrency` | `4` | Max concurrent API calls |
| `--budget-usd` | `0` (disabled) | Total cost budget |
| `--max-items` | `0` (all) | Max items to process |
| `--skip-missing/--no-skip-missing` | `--skip-missing` | Skip missing WSIs |
| `--resume/--no-resume` | `--resume` | Resume from checkpoint |
| `-v, --verbose` | 0 | Verbosity level |
| `--json` | False | Output as JSON |

### Examples

```bash
# Full GTEx benchmark
giant benchmark gtex --provider openai -v

# Quick test (5 items)
giant benchmark tcga --max-items 5 -v

# High concurrency with resume
giant benchmark panda --concurrency 8 --resume -v

# Cost-limited run
giant benchmark gtex --budget-usd 10.00 -v
```

---

## `giant download`

Download benchmark datasets from HuggingFace.

```bash
giant download [dataset] [options]
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `DATASET` | `multipathqa` | Dataset to download |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `-o, --output-dir` | `data` | Output directory |
| `--force` | False | Re-download if exists |
| `-v, --verbose` | 0 | Verbosity level |
| `--json` | False | Output as JSON |

### Examples

```bash
# Download MultiPathQA metadata
giant download multipathqa

# Force re-download
giant download multipathqa --force
```

---

## `giant check-data`

Validate that WSI files for a benchmark exist locally.

```bash
giant check-data <dataset> [options]
```

### Arguments

| Argument | Values | Description |
|----------|--------|-------------|
| `DATASET` | `tcga`, `panda`, `gtex`, `tcga_expert_vqa`, `tcga_slidebench` | Dataset name |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--csv-path` | `data/multipathqa/MultiPathQA.csv` | Path to benchmark CSV |
| `--wsi-root` | `data/wsi` | Root directory for WSIs |
| `-v, --verbose` | 0 | Verbosity (shows missing files) |
| `--json` | False | Output as JSON |

### Examples

```bash
# Check GTEx data
giant check-data gtex

# Verbose output showing missing files
giant check-data tcga -v

# JSON output
giant check-data panda --json
```

### Output

```
All WSIs present for gtex: 191/191 under data/wsi
```

---

## `giant visualize`

Generate interactive visualization of navigation trajectory.

```bash
giant visualize <trajectory_path> [options]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `TRAJECTORY_PATH` | Yes | Path to trajectory JSON file |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `-o, --output` | Auto-generated | Output HTML file path |
| `--open/--no-open` | `--open` | Open in browser |
| `-v, --verbose` | 0 | Verbosity level |
| `--json` | False | Output as JSON |

### Examples

```bash
# Visualize and open in browser
giant visualize trajectory.json

# Save without opening
giant visualize trajectory.json --no-open -o output.html
```

---

## Environment Variables

| Variable | Required For | Description |
|----------|--------------|-------------|
| `OPENAI_API_KEY` | `--provider openai` | OpenAI API key |
| `ANTHROPIC_API_KEY` | `--provider anthropic` | Anthropic API key |

---

## Verbosity Levels

| Level | Flag | Output |
|-------|------|--------|
| 0 | (none) | Errors and results only |
| 1 | `-v` | Info messages |
| 2 | `-vv` | Debug messages |
| 3+ | `-vvv` | Trace messages |

---

## See Also

- [Running Inference](../guides/running-inference.md)
- [Running Benchmarks](../guides/running-benchmarks.md)
- [Configuration](configuration.md)
