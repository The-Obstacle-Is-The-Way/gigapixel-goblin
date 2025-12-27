# Contributing

Thank you for your interest in contributing to GIANT! This guide covers how to set up your development environment and submit contributions.

## Development Setup

### Prerequisites

- Python 3.11+
- OpenSlide library
- uv package manager (recommended)
- Git

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/The-Obstacle-Is-The-Way/gigapixel-goblin.git
cd gigapixel-goblin

# Install with dev dependencies
uv sync --dev

# Activate environment
source .venv/bin/activate

# Verify installation
giant version
pytest tests/unit -x
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 2. Make Changes

Follow the coding standards below.

### 3. Run Tests

```bash
# Unit tests (fast)
pytest tests/unit

# With coverage
pytest tests/unit --cov=giant --cov-report=term-missing

# Specific module
pytest tests/unit/llm/
```

### 4. Run Linting

```bash
# Check code style
ruff check .

# Auto-fix issues
ruff check . --fix

# Format code
ruff format .

# Type checking
mypy src/giant
```

### 5. Commit Changes

```bash
git add .
git commit -m "feat: add new feature description"
```

Follow [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | Use For |
|--------|---------|
| `feat:` | New features |
| `fix:` | Bug fixes |
| `docs:` | Documentation |
| `refactor:` | Code refactoring |
| `test:` | Test changes |
| `chore:` | Maintenance |

### 6. Push and Create PR

```bash
git push -u origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

## Coding Standards

### Python Style

- Follow PEP 8 with Ruff enforcement
- Maximum line length: 88 characters
- Use type hints for all public functions
- Docstrings for all public classes and functions

### Example

```python
"""Module docstring explaining purpose."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class ExampleClass:
    """Class docstring.

    Attributes:
        name: Description of attribute.
        value: Description of attribute.
    """

    name: str
    value: int

    def process(self, input_path: Path) -> str:
        """Process the input.

        Args:
            input_path: Path to input file.

        Returns:
            Processed result string.

        Raises:
            ValueError: If input is invalid.
        """
        if not input_path.exists():
            raise ValueError(f"Path does not exist: {input_path}")
        return f"Processed: {self.name}"
```

### Imports

```python
# Standard library
import os
from pathlib import Path

# Third-party
import numpy as np
from pydantic import BaseModel

# Local
from giant.geometry import Region
from giant.llm import LLMProvider
```

### Error Handling

- Use specific exception types
- Never catch bare `Exception` unless re-raising
- Include context in error messages

```python
# Good
try:
    result = process(data)
except ValueError as e:
    logger.error("Processing failed: %s", e)
    raise ProcessingError(f"Failed to process {data.id}") from e

# Bad
try:
    result = process(data)
except:
    pass
```

## Test Guidelines

### Test-Driven Development

This project follows TDD:

1. Write a failing test
2. Implement the feature
3. Refactor

### Test Organization

```
tests/
├── unit/           # Fast, isolated tests
│   └── module/
│       └── test_feature.py
└── integration/    # Tests requiring external resources
    └── module/
        └── test_integration.py
```

### Test Naming

```python
def test_feature_does_expected_thing() -> None:
    """Test that feature does X when Y."""
    ...

def test_feature_raises_on_invalid_input() -> None:
    """Test that feature raises ValueError for invalid input."""
    ...
```

### Fixtures

Use pytest fixtures for common setup:

```python
# conftest.py
@pytest.fixture
def sample_region() -> Region:
    return Region(x=100, y=200, width=50, height=50)

# test_feature.py
def test_crop_uses_region(sample_region: Region) -> None:
    result = crop(sample_region)
    assert result is not None
```

### Mocking

Use mocks for external dependencies:

```python
from unittest.mock import AsyncMock, MagicMock

def test_agent_calls_provider(mocker: MockerFixture) -> None:
    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.generate_response = AsyncMock(return_value=mock_response)

    agent = GIANTAgent(provider=mock_provider, ...)
    result = asyncio.run(agent.run())

    mock_provider.generate_response.assert_called_once()
```

## Documentation

### Docstrings

Use Google-style docstrings:

```python
def function(arg1: str, arg2: int = 10) -> dict[str, int]:
    """Short description.

    Longer description if needed. Can span multiple lines
    and include examples.

    Args:
        arg1: Description of arg1.
        arg2: Description of arg2. Defaults to 10.

    Returns:
        Dictionary mapping strings to integers.

    Raises:
        ValueError: If arg1 is empty.

    Example:
        >>> function("test", 20)
        {"test": 20}
    """
```

### MkDocs Documentation

Documentation lives in `docs/`. To preview:

```bash
# Install mkdocs
pip install mkdocs-material

# Serve locally
mkdocs serve
```

Then open http://localhost:8000.

## Pull Request Guidelines

### Before Submitting

- [ ] All tests pass (`pytest tests/unit`)
- [ ] No linting errors (`ruff check .`)
- [ ] Type checking passes (`mypy src/giant`)
- [ ] Code is formatted (`ruff format .`)
- [ ] Docstrings added for new code
- [ ] Tests added for new features

### PR Description

Include:

1. **Summary** - What the change does
2. **Motivation** - Why it's needed
3. **Test plan** - How it was tested

### Review Process

1. Automated checks must pass
2. At least one maintainer review
3. Address feedback
4. Merge when approved

## Bug Reports

### Where to Report

- GitHub Issues: https://github.com/The-Obstacle-Is-The-Way/gigapixel-goblin/issues

### Bug Report Template

```markdown
## Description
Brief description of the bug.

## Steps to Reproduce
1. Step one
2. Step two
3. Step three

## Expected Behavior
What should happen.

## Actual Behavior
What actually happens.

## Environment
- OS:
- Python version:
- GIANT version:
- OpenSlide version:
```

## Questions?

- Check existing issues
- Read the documentation
- Open a new issue with the `question` label

## See Also

- [Testing](testing.md)
- [Project Structure](../reference/project-structure.md)
- [Architecture](../concepts/architecture.md)
