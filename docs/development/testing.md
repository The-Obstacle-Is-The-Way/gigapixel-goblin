# Testing

This guide covers GIANT's testing practices and conventions.

## Test Organization

```
tests/
├── conftest.py             # Shared fixtures
├── unit/                   # Unit tests
│   ├── agent/
│   ├── llm/
│   ├── core/
│   ├── geometry/
│   ├── eval/
│   └── cli/
└── integration/            # Integration tests
    ├── wsi/
    └── llm/
```

## Running Tests

### Unit Tests (Fast)

```bash
# All unit tests
pytest tests/unit

# Stop on first failure
pytest tests/unit -x

# Specific module
pytest tests/unit/llm/

# Single test file
pytest tests/unit/llm/test_openai_client.py

# Single test
pytest tests/unit/llm/test_openai_client.py::test_generate_response
```

### With Coverage

```bash
# Generate coverage report
pytest tests/unit --cov=giant --cov-report=term-missing

# HTML coverage report
pytest tests/unit --cov=giant --cov-report=html
open htmlcov/index.html
```

### Integration Tests

```bash
# Requires real WSI files
pytest tests/integration/wsi/

# Requires API keys (costs money!)
GIANT_RUN_LIVE_TESTS=1 pytest tests/integration/llm/
```

## Test Markers

### Available Markers

| Marker | Description | Default |
|--------|-------------|---------|
| `@pytest.mark.cost` | Requires live API, costs money | Skipped |
| `@pytest.mark.integration` | Requires real resources | Included |
| `@pytest.mark.live` | Requires live external service | Skipped |

### Usage

```python
import pytest

@pytest.mark.cost
async def test_real_api_call():
    """This test calls a real API and costs money."""
    ...

@pytest.mark.integration
def test_with_real_wsi():
    """This test requires real WSI files."""
    ...
```

### Running Marked Tests

```bash
# Skip cost tests (default)
pytest tests/

# Include cost tests (requires GIANT_RUN_LIVE_TESTS=1)
GIANT_RUN_LIVE_TESTS=1 pytest -m cost

# Only integration tests
pytest -m integration

# Exclude integration tests
pytest -m "not integration"
```

## Writing Tests

### Test Structure

```python
"""Tests for giant.module.feature module."""

import pytest
from giant.module.feature import FeatureClass


class TestFeatureClass:
    """Tests for FeatureClass."""

    def test_basic_functionality(self) -> None:
        """Test that basic feature works correctly."""
        # Arrange
        obj = FeatureClass(name="test")

        # Act
        result = obj.process()

        # Assert
        assert result == "expected"

    def test_raises_on_invalid_input(self) -> None:
        """Test that invalid input raises ValueError."""
        obj = FeatureClass(name="")

        with pytest.raises(ValueError) as exc_info:
            obj.process()

        assert "empty" in str(exc_info.value)
```

### Async Tests

```python
import pytest

@pytest.mark.asyncio
async def test_async_function() -> None:
    """Test async function."""
    result = await async_function()
    assert result is not None
```

### Parametrized Tests

```python
import pytest

@pytest.mark.parametrize("input,expected", [
    ("case1", "result1"),
    ("case2", "result2"),
    ("case3", "result3"),
])
def test_multiple_cases(input: str, expected: str) -> None:
    """Test multiple input cases."""
    assert process(input) == expected
```

## Fixtures

### Shared Fixtures (`conftest.py`)

```python
# tests/conftest.py
import pytest
from giant.geometry import Region

@pytest.fixture
def sample_region() -> Region:
    """Create a sample Region for testing."""
    return Region(x=100, y=200, width=50, height=50)

@pytest.fixture
def mock_wsi_path(tmp_path):
    """Create a mock WSI path."""
    wsi = tmp_path / "test.svs"
    wsi.touch()
    return wsi
```

### Module-Specific Fixtures

```python
# tests/unit/llm/conftest.py
import pytest
from unittest.mock import MagicMock, AsyncMock
from giant.llm.protocol import LLMResponse, StepResponse

@pytest.fixture
def mock_llm_response() -> LLMResponse:
    """Create a mock LLM response."""
    return LLMResponse(
        step_response=StepResponse(
            reasoning="Test reasoning",
            action={"action_type": "answer", "answer_text": "Test answer"}
        ),
        usage=TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.01,
        ),
        model="gpt-5.2",
        latency_ms=500.0,
    )
```

## Mocking

### Basic Mocking

```python
from unittest.mock import MagicMock, patch

def test_with_mock():
    mock_client = MagicMock()
    mock_client.call.return_value = "result"

    result = function_under_test(client=mock_client)

    mock_client.call.assert_called_once()
    assert result == "result"
```

### Async Mocking

```python
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_async_with_mock():
    mock_provider = MagicMock()
    mock_provider.generate_response = AsyncMock(return_value=mock_response)

    result = await agent.run(provider=mock_provider)

    mock_provider.generate_response.assert_called()
```

### Patching

```python
from unittest.mock import patch

def test_with_patch():
    with patch("giant.module.external_function") as mock_func:
        mock_func.return_value = "mocked"

        result = function_that_calls_external()

        assert result == "mocked"
```

### Using pytest-mock

```python
def test_with_mocker(mocker):
    mock_func = mocker.patch("giant.module.function")
    mock_func.return_value = "mocked"

    result = function_under_test()

    assert result == "mocked"
```

## Test Coverage

### Coverage Requirements

- Minimum: 90% (enforced in CI)
- Target: 95%+

### Checking Coverage

```bash
# Terminal report
pytest tests/unit --cov=giant --cov-report=term-missing

# HTML report
pytest tests/unit --cov=giant --cov-report=html

# Fail if below threshold
pytest tests/unit --cov=giant --cov-fail-under=90
```

### Ignoring Coverage

For code that can't be tested:

```python
if TYPE_CHECKING:  # pragma: no cover
    from expensive.import import Type
```

## Test Data

### Sample WSI Files

For integration tests, download OpenSlide test data:

```bash
mkdir -p tests/integration/wsi/data
curl -L -o tests/integration/wsi/data/CMU-1-Small-Region.svs \
    https://openslide.cs.cmu.edu/download/openslide-testdata/Aperio/CMU-1-Small-Region.svs
```

### Using Test Data

```python
import pytest
from pathlib import Path

@pytest.fixture
def test_wsi_path() -> Path:
    """Path to test WSI file."""
    path = Path("tests/integration/wsi/data/CMU-1-Small-Region.svs")
    if not path.exists():
        pytest.skip("Test WSI not available")
    return path
```

## Common Patterns

### Testing Exceptions

```python
def test_raises_on_error():
    with pytest.raises(ValueError) as exc_info:
        function_that_raises()

    assert "specific message" in str(exc_info.value)
```

### Testing Warnings

```python
def test_emits_warning():
    with pytest.warns(DeprecationWarning):
        deprecated_function()
```

### Temporary Files

```python
def test_with_temp_file(tmp_path):
    test_file = tmp_path / "test.json"
    test_file.write_text('{"key": "value"}')

    result = load_json(test_file)

    assert result["key"] == "value"
```

## CI Integration

Tests run automatically on:

- Pull requests
- Pushes to main/dev branches

CI configuration enforces:

- All unit tests pass
- Coverage >= 90%
- No linting errors
- Type checking passes

## Troubleshooting

### Test Not Found

```bash
# Ensure correct path
pytest tests/unit/module/test_file.py -v

# Check for import errors
python -c "import tests.unit.module.test_file"
```

### Fixture Not Found

```bash
# List available fixtures
pytest --fixtures

# Check conftest.py location
```

### Async Test Issues

```bash
# Ensure pytest-asyncio is installed
pip install pytest-asyncio

# Check marker is present
@pytest.mark.asyncio
async def test_async(): ...
```

## See Also

- [Contributing](contributing.md)
- [Project Structure](../reference/project-structure.md)
- [Architecture](../concepts/architecture.md)
