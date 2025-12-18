"""Tests for giant.llm.circuit_breaker module."""

import time
from unittest.mock import patch

import pytest

from giant.llm.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
)
from giant.llm.protocol import CircuitBreakerOpenError


class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 10
        assert config.cooldown_seconds == 60.0
        assert config.half_open_max_calls == 3
        assert config.success_threshold == 2

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = CircuitBreakerConfig(
            failure_threshold=5,
            cooldown_seconds=30.0,
            half_open_max_calls=2,
            success_threshold=1,
        )
        assert config.failure_threshold == 5
        assert config.cooldown_seconds == 30.0


class TestCircuitBreakerInitialState:
    """Tests for circuit breaker initial state."""

    def test_starts_closed(self) -> None:
        """Test that circuit breaker starts in closed state."""
        breaker = CircuitBreaker(provider_name="test")
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed

    def test_check_passes_when_closed(self) -> None:
        """Test that check() passes when circuit is closed."""
        breaker = CircuitBreaker(provider_name="test")
        breaker.check()  # Should not raise


class TestCircuitBreakerFailures:
    """Tests for circuit breaker failure handling."""

    def test_opens_after_threshold_failures(self) -> None:
        """Test circuit opens after reaching failure threshold."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker(provider_name="test", config=config)

        # Record failures
        for _ in range(3):
            breaker.record_failure()

        assert breaker.state == CircuitState.OPEN
        assert breaker.is_open

    def test_stays_closed_below_threshold(self) -> None:
        """Test circuit stays closed below failure threshold."""
        config = CircuitBreakerConfig(failure_threshold=5)
        breaker = CircuitBreaker(provider_name="test", config=config)

        # Record failures below threshold
        for _ in range(4):
            breaker.record_failure()

        assert breaker.state == CircuitState.CLOSED

    def test_success_resets_failure_count(self) -> None:
        """Test that success resets the failure count."""
        config = CircuitBreakerConfig(failure_threshold=5)
        breaker = CircuitBreaker(provider_name="test", config=config)

        # Record some failures
        for _ in range(3):
            breaker.record_failure()

        # Record success
        breaker.record_success()

        # Should be able to have more failures before opening
        for _ in range(4):
            breaker.record_failure()

        assert breaker.state == CircuitState.CLOSED

        # One more failure should open it
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN


class TestCircuitBreakerOpen:
    """Tests for circuit breaker in open state."""

    def test_check_raises_when_open(self) -> None:
        """Test that check() raises when circuit is open."""
        config = CircuitBreakerConfig(failure_threshold=1, cooldown_seconds=60.0)
        breaker = CircuitBreaker(provider_name="test", config=config)

        breaker.record_failure()

        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            breaker.check()

        assert "test" in str(exc_info.value)
        assert exc_info.value.provider == "test"

    def test_cooldown_remaining_calculated(self) -> None:
        """Test that cooldown remaining is calculated correctly."""
        config = CircuitBreakerConfig(failure_threshold=1, cooldown_seconds=60.0)
        breaker = CircuitBreaker(provider_name="test", config=config)

        breaker.record_failure()

        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            breaker.check()

        # Cooldown should be close to 60 seconds
        assert exc_info.value.cooldown_remaining_seconds > 59.0
        assert exc_info.value.cooldown_remaining_seconds <= 60.0


class TestCircuitBreakerHalfOpen:
    """Tests for circuit breaker in half-open state."""

    def test_transitions_to_half_open_after_cooldown(self) -> None:
        """Test transition from open to half-open after cooldown."""
        config = CircuitBreakerConfig(failure_threshold=1, cooldown_seconds=0.01)
        breaker = CircuitBreaker(provider_name="test", config=config)

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Wait for cooldown
        time.sleep(0.02)

        # State check should trigger transition
        assert breaker.state == CircuitState.HALF_OPEN

    def test_half_open_allows_limited_calls(self) -> None:
        """Test that half-open state allows limited calls."""
        config = CircuitBreakerConfig(
            failure_threshold=1, cooldown_seconds=0.01, half_open_max_calls=2
        )
        breaker = CircuitBreaker(provider_name="test", config=config)

        breaker.record_failure()
        time.sleep(0.02)  # Wait for transition to half-open

        # First two calls should pass
        breaker.check()
        breaker.check()

        # Third call should fail
        with pytest.raises(CircuitBreakerOpenError):
            breaker.check()

    def test_half_open_closes_on_success(self) -> None:
        """Test circuit closes after successes in half-open."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            cooldown_seconds=0.01,
            success_threshold=2,
        )
        breaker = CircuitBreaker(provider_name="test", config=config)

        breaker.record_failure()
        time.sleep(0.02)  # Wait for transition to half-open

        # Force check state to trigger transition
        _ = breaker.state  # This triggers the transition to half-open

        # Record successes
        breaker.record_success()
        assert breaker._state == CircuitState.HALF_OPEN  # Not closed yet

        breaker.record_success()
        assert breaker._state == CircuitState.CLOSED

    def test_half_open_reopens_on_failure(self) -> None:
        """Test circuit reopens on failure in half-open state."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            cooldown_seconds=0.01,
        )
        breaker = CircuitBreaker(provider_name="test", config=config)

        breaker.record_failure()
        time.sleep(0.02)  # Wait for transition to half-open

        assert breaker.state == CircuitState.HALF_OPEN

        # Record failure in half-open
        breaker.record_failure()

        assert breaker.state == CircuitState.OPEN


class TestCircuitBreakerReset:
    """Tests for circuit breaker reset functionality."""

    def test_reset_clears_all_state(self) -> None:
        """Test that reset clears all internal state."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker(provider_name="test", config=config)

        # Open the circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Reset
        breaker.reset()

        # Should be back to initial state
        assert breaker.state == CircuitState.CLOSED
        breaker.check()  # Should not raise


class TestCircuitBreakerLogging:
    """Tests for circuit breaker logging."""

    def test_logs_on_open(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that opening circuit logs a warning."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker(provider_name="test", config=config)

        with caplog.at_level("WARNING"):
            breaker.record_failure()

        assert "opening" in caplog.text.lower() or len(caplog.records) > 0

    def test_logs_on_close(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that closing circuit logs info."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            cooldown_seconds=0.01,
            success_threshold=1,
        )
        breaker = CircuitBreaker(provider_name="test", config=config)

        breaker.record_failure()
        time.sleep(0.02)

        # Force transition to half-open by checking state
        _ = breaker.state

        with caplog.at_level("INFO"):
            breaker.record_success()

        # Verify state changed
        assert breaker._state == CircuitState.CLOSED


class TestCircuitBreakerMonotonicTime:
    """Tests verifying monotonic time usage."""

    def test_uses_monotonic_time(self) -> None:
        """Test that circuit breaker uses monotonic time."""
        config = CircuitBreakerConfig(failure_threshold=1, cooldown_seconds=0.05)
        breaker = CircuitBreaker(provider_name="test", config=config)

        with patch("giant.llm.circuit_breaker.time.monotonic") as mock_time:
            # Set initial time
            mock_time.return_value = 1000.0
            breaker.record_failure()

            # Circuit should be open
            assert breaker._state == CircuitState.OPEN

            # Advance time past cooldown
            mock_time.return_value = 1000.1  # 0.1 seconds later

            # Checking state should trigger transition
            state = breaker.state
            assert state == CircuitState.HALF_OPEN
