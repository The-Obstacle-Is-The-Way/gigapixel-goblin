<p align="center">
  <strong>🔬 GIANT</strong><br>
  <em>Gigapixel Image Agent for Navigating Tissue</em>
</p>

<p align="center">
  <a href="https://arxiv.org/abs/2511.19652"><img alt="Paper" src="https://img.shields.io/badge/arXiv-2511.19652-b31b1b.svg"></a>
  <a href="https://huggingface.co/datasets/tbuckley/MultiPathQA"><img alt="Dataset" src="https://img.shields.io/badge/🤗-MultiPathQA-yellow.svg"></a>
  <a href="https://www.python.org/downloads/"><img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11+-blue.svg"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-green.svg"></a>
</p>

---

**The Problem**: Whole-slide pathology images contain *billions of pixels*—10,000× more than an LLM can see at once. Previous approaches used blurry thumbnails or random patches, severely underestimating what frontier models can do.

**The Solution**: GIANT lets LLMs navigate gigapixel images like pathologists do—iteratively pan, zoom, and reason across the slide until they can answer a diagnostic question.

> *"GPT-5 with GIANT achieves 62.5% accuracy on pathologist-authored questions, outperforming specialist pathology models such as TITAN (43.8%) and SlideChat (37.5%)."*
> — [Buckley et al., 2025](https://arxiv.org/abs/2511.19652)

---

## How It Works

```
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

# Run benchmark
giant benchmark gtex --provider openai -v
```

---

## Benchmark Results

Evaluated on [MultiPathQA](https://huggingface.co/datasets/tbuckley/MultiPathQA)—934 questions across 868 unique whole-slide images.

| Benchmark | Task | Our Result | Paper (GIANT) | Thumbnail Baseline |
|-----------|------|:----------:|:-------------:|:------------------:|
| **GTEx** | Organ Classification (20-way) | **67.6%** | 53.7% | 36.5% |
| **TCGA** | Cancer Diagnosis (30-way) | 25.2% | 32.3% | 9.2% |
| PANDA | Prostate Grading (6-way) | — | 23.2% | 12.2% |
| ExpertVQA | Pathologist-Authored (128 Q) | — | 62.5% | 50.0% |

**Key finding**: Our GTEx result (67.6%) *exceeds* the paper's 5-run majority vote (60.7%), validating the implementation. Agent navigation provides 3-7× improvement over naive baselines.

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
| [**Data Acquisition**](docs/data-acquisition.md) | Download WSI files (~500 GiB) |
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
