<p align="center">
  <strong>🔬 GIANT</strong><br>
  <em>Gigapixel Image Agent for Navigating Tissue</em>
</p>

<p align="center">
  <a href="https://arxiv.org/abs/2511.19652"><img alt="Paper" src="https://img.shields.io/badge/arXiv-2511.19652-b31b1b.svg"></a>
  <a href="https://huggingface.co/datasets/tbuckley/MultiPathQA"><img alt="Dataset" src="https://img.shields.io/badge/🤗-MultiPathQA-yellow.svg"></a>
  <a href="https://www.python.org/downloads/"><img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11+-blue.svg"></a>
  <a href="LICENSE"><img alt="License: Apache-2.0" src="https://img.shields.io/badge/License-Apache_2.0-blue.svg"></a>
</p>

---

**The Problem**: Whole-slide pathology images contain *billions of pixels*—10,000× more than an LLM can see at once. Previous approaches used blurry thumbnails or random patches, severely underestimating what frontier models can do.

**The Solution**: GIANT lets LLMs navigate gigapixel images like pathologists do—iteratively pan, zoom, and reason across the slide until they can answer a diagnostic question.

> *"GPT-5 with GIANT achieves 62.5% accuracy on pathologist-authored questions, outperforming specialist pathology models such as TITAN (43.8%) and SlideChat (37.5%)."*
> — [Buckley et al., 2025](https://arxiv.org/abs/2511.19652)

---

## How It Works

```text
1. LOAD        →  Open gigapixel WSI, generate thumbnail with coordinate guides
2. OBSERVE     →  LLM sees current view + conversation history
3. REASON      →  "I see suspicious tissue at (45000, 32000). Let me zoom in..."
4. ACT         →  Crop high-resolution region OR provide final answer
5. REPEAT      →  Continue until confident diagnosis (max 20 steps)
```

The agent accumulates evidence across multiple zoom levels—just like a pathologist scanning a slide.

---

## Quick Start

```bash
# Install
uv sync && source .venv/bin/activate

# Configure API
export OPENAI_API_KEY=sk-...

# Run on a slide
giant run /path/to/slide.svs -q "What type of tissue is this?"

# Run benchmark (requires MultiPathQA CSV + WSI files; see docs/data/data-acquisition.md)
giant benchmark gtex --provider openai -v
```

---

## Benchmark Results

Evaluated on [MultiPathQA](https://huggingface.co/datasets/tbuckley/MultiPathQA)—934 questions across 862 unique whole-slide images.

| Benchmark | Task | Our Result | Paper (GIANT) | Paper (GIANT x5) | Thumbnail Baseline |
|-----------|------|:----------:|:-------------:|:----------------:|:------------------:|
| **GTEx** | Organ Classification (20-way) | **70.3%** | 53.7% ± 3.4% | 60.7% ± 3.2% | 36.5% ± 3.4% |
| **ExpertVQA** | Pathologist-Authored (128 Q) | **60.1%** | 57.0% ± 4.5% | 62.5% ± 4.4% | 50.0% ± 4.4% |
| SlideBench | Visual QA (197 Q) | **51.8%** | 58.9% ± 3.5% | 59.4% ± 3.4% | 54.8% ± 3.5% |
| TCGA | Cancer Diagnosis (30-way) | **26.2%** | 32.3% ± 3.5% | 29.3% ± 3.3% | 9.2% ± 1.9% |
| PANDA | Prostate Grading (6-way) | **20.3%** | 23.2% ± 2.3% | 25.4% ± 2.0% | 12.2% ± 2.2% |

All 5 MultiPathQA benchmarks complete. See `docs/results/benchmark-results.md` for detailed analysis.

**Key findings**:
- **GTEx (70.3%)** and **ExpertVQA (60.1%)** *exceed* the paper's single-run GIANT results
- Agent navigation provides up to ~3× improvement over thumbnail baselines
- Total benchmark cost: **$124.64** across 934 questions

---

## Supported Models

| Provider | Model | Status |
|----------|-------|:------:|
| OpenAI | `gpt-5.2` | ✅ Default |
| Anthropic | `claude-sonnet-4-5-20250929` | ✅ Supported |
| Google | `gemini-3-pro-preview` | 🔜 Planned |

---

## Documentation

| Section | Description |
|---------|-------------|
| [**Installation**](docs/getting-started/installation.md) | Environment setup |
| [**Quickstart**](docs/getting-started/quickstart.md) | First inference in 5 minutes |
| [**Architecture**](docs/concepts/architecture.md) | System design and components |
| [**Algorithm**](docs/concepts/algorithm.md) | Navigation loop explained |
| [**Running Benchmarks**](docs/guides/running-benchmarks.md) | Reproduce paper results |
| [**Configuring Providers**](docs/guides/configuring-providers.md) | API key setup |
| [**Data Acquisition**](docs/data/data-acquisition.md) | Download WSI files (~500 GiB) |
| [**CLI Reference**](docs/reference/cli.md) | Command-line options |

---

## Why This Matters

**For Clinicians**: Frontier LLMs can now reason over full pathology slides—not just patches. This opens doors for AI-assisted diagnosis, second opinions, and education.

**For Researchers**: A reproducible benchmark (MultiPathQA) and framework for evaluating LLM capabilities on gigapixel medical images. Proves that *how* you test matters as much as *what* you test.

**For Developers**: Production-ready implementation with 90% test coverage, strict typing, resumable benchmarks, cost tracking, and trajectory visualization.

---

## Citation

```bibtex
@article{buckley2025navigating,
  title={Navigating Gigapixel Pathology Images with Large Multimodal Models},
  author={Buckley, Thomas A. and Weihrauch, Kian R. and Latham, Katherine and
          Zhou, Andrew Z. and Manrai, Padmini A. and Manrai, Arjun K.},
  journal={arXiv preprint arXiv:2511.19652},
  year={2025}
}
```

---

## Links

- **Paper**: [arXiv:2511.19652](https://arxiv.org/abs/2511.19652)
- **Dataset**: [MultiPathQA on HuggingFace](https://huggingface.co/datasets/tbuckley/MultiPathQA)
- **Documentation**: [Full Docs](docs/index.md)

---

<p align="center">
  <em>Built for reproducible research in computational pathology.</em>
</p>
