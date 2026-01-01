# Installation

This guide walks you through setting up GIANT on your local machine.

## Prerequisites

- **Python 3.11+** (tested with 3.11, 3.12)
- **OpenSlide** library (for reading whole-slide images)
- **uv** package manager (recommended) or pip

## System Dependencies

### macOS

```bash
# Install OpenSlide
brew install openslide

# Install uv (recommended package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Ubuntu/Debian

```bash
# Install OpenSlide
sudo apt-get install openslide-tools python3-openslide

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Windows

```powershell
# OpenSlide Windows binaries: https://openslide.org/download/
# Add OpenSlide bin directory to PATH

# Install uv
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Clone and Install

```bash
# Clone the repository
git clone https://github.com/The-Obstacle-Is-The-Way/gigapixel-goblin.git
cd gigapixel-goblin

# Install dependencies with uv (recommended)
uv sync

# Activate the virtual environment
source .venv/bin/activate
```

## Verify Installation

```bash
# Check GIANT version
giant version

# Verify OpenSlide is working
python -c "import openslide; print(f'OpenSlide version: {openslide.__version__}')"

# Run unit tests
uv run pytest tests/unit -x
```

## API Keys

GIANT requires API keys for LLM providers. Create a `.env` file in the project root:

```bash
# .env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

See [Configuring Providers](../guides/configuring-providers.md) for detailed setup instructions.

## Next Steps

- [Quickstart](quickstart.md) - Run your first inference
- [Data Acquisition](../data/data-acquisition.md) - Download WSI files for benchmarks
- [Configuring Providers](../guides/configuring-providers.md) - Set up OpenAI/Anthropic
