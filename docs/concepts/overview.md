# What is GIANT?

**GIANT** (Gigapixel Image Agent for Navigating Tissue) is an agentic system that uses large language models (LLMs) to autonomously navigate whole-slide images (WSIs) for pathology analysis.

## The Problem

Whole-slide images are massive - often **100,000+ pixels** on each side, resulting in **gigapixel-scale** images. A typical WSI can be 50,000 x 80,000 pixels or larger.

This creates fundamental challenges:

1. **Too large for direct analysis**: LLMs have input size limits (~1-2K pixels typically)
2. **Information overload**: Most of the slide is background or irrelevant tissue
3. **Multi-scale features**: Diagnosis requires both architectural patterns (low magnification) and cellular details (high magnification)

## The Solution

GIANT treats WSI analysis as a **navigation problem**. Instead of trying to analyze the entire slide at once, an LLM-powered agent:

1. **Starts with a thumbnail** - A low-resolution overview with coordinate axis guides
2. **Iteratively zooms in** - Selects regions of interest based on the question
3. **Accumulates evidence** - Remembers what it has seen across navigation steps
4. **Provides an answer** - When sufficient evidence is gathered

This mimics how pathologists work: scan at low power, identify regions of interest, zoom in for cellular detail.

## Key Innovations

### Axis Guides

The thumbnail is overlaid with coordinate markers showing **Level-0 pixel positions**. This allows the LLM to specify exact crop coordinates using natural language reasoning:

> "I can see a suspicious region around coordinates (45000, 32000). Let me zoom in there..."

### Multi-turn Context

The agent maintains conversation history, remembering:
- Previously examined regions
- Observations and reasoning at each step
- The original question being answered

### Structured Actions

The LLM outputs structured JSON actions:

```json
{
  "reasoning": "The thumbnail shows a dark region that may be tumor...",
  "action": {
    "action_type": "crop",
    "x": 45000,
    "y": 32000,
    "width": 10000,
    "height": 10000
  }
}
```

Or when ready to answer:

```json
{
  "reasoning": "Based on the cellular morphology observed...",
  "action": {
    "action_type": "answer",
    "answer_text": "This is adenocarcinoma, moderately differentiated."
  }
}
```

## Supported Tasks

GIANT can answer various pathology questions:

| Task Type | Example Question |
|-----------|------------------|
| **Classification** | "What organ is this tissue from?" |
| **Diagnosis** | "What type of cancer is present?" |
| **Grading** | "What is the Gleason grade?" |
| **VQA** | "Are there mitotic figures visible?" |

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    GIANTAgent                       │
│                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐       │
│  │WSIReader │───▶│CropEngine│───▶│OverlayGen│       │
│  └──────────┘    └──────────┘    └──────────┘       │
│        │              │               │             │
│        └──────────────┴───────────────┘             │
│                       │                             │
│                       ▼                             │
│              ┌──────────────┐                       │
│              │ContextManager│                       │
│              └──────────────┘                       │
│                       │                             │
│                       ▼                             │
│              ┌──────────────┐                       │
│              │ LLMProvider  │◀──▶ OpenAI/Anthropic  │
│              └──────────────┘                       │
│                       │                             │
│                       ▼                             │
│              ┌──────────────┐                       │
│              │  Trajectory  │───▶ Evaluation        │
│              └──────────────┘                       │
└─────────────────────────────────────────────────────┘
```

## Research Origin

GIANT is based on the paper:

> **GIANT: Gigapixel Image Agent for Navigating Tissue**
> arXiv:2511.19652

This implementation reproduces and extends the paper's methodology, achieving competitive results on the MultiPathQA benchmark.

## Next Steps

- [Architecture](architecture.md) - Detailed system design
- [Algorithm](algorithm.md) - The core navigation algorithm
- [Quickstart](../getting-started/quickstart.md) - Try it yourself
