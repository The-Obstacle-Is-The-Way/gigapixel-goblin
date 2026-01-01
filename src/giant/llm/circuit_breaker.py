"""Circuit breaker for LLM API failure containment.

This module implements a circuit breaker pattern to protect against cascading
failures when LLM APIs become unavailable. It prevents:

- Budget overruns from retrying failing requests
- Rate limit exhaustion from hammering an unhealthy API
- User experience degradation from long timeouts

The circuit breaker has three states:
- CLOSED: Normal operation, requests pass through
- OPEN: API is unhealthy, requests fail immediately
- HALF_OPEN: Testing if API recovered, limited requests allowed

Per Spec-06, this is used by all LLM providers.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

from giant.llm.protocol import CircuitBreakerOpenError
from giant.utils.logging import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True)
class CircuitBreakerConfig:
    """Configuration for the circuit breaker.

    Attributes:
        failure_threshold: Number of consecutive failures to open circuit.
        cooldown_seconds: Time to wait before transitioning to half-open.
        half_open_max_calls: Max calls allowed in half-open state.
        success_threshold: Successes needed in half-open to close circuit.
    """

    failure_threshold: int = 10
    cooldown_seconds: float = 60.0
    half_open_max_calls: int = 3
    success_threshold: int = 2


@dataclass
class CircuitBreaker:
    """Circuit breaker for protecting LLM API calls.

    Usage:
        breaker = CircuitBreaker(provider_name="openai")

        # Before making API call
        breaker.check()  # Raises if circuit is open

        try:
            result = await api_call()
            breaker.record_success()
        except Exception as e:
            breaker.record_failure()
            raise
    """

    provider_name: str
    config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)

    # Internal state
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: float | None = field(default=None, init=False)
    _half_open_call_count: int = field(default=0, init=False)

    @property
    def state(self) -> CircuitState:
        return self._state

    def refresh_state(self, now: float | None = None) -> None:
        """Refresh time-based state transitions.

        Transitions from OPEN -> HALF_OPEN once the configured cooldown has elapsed.
        """
        if self._state != CircuitState.OPEN or self._last_failure_time is None:
            return

        if now is None:
            now = time.monotonic()
        elapsed = now - self._last_failure_time
        if elapsed >= self.config.cooldown_seconds:
            self._transition_to_half_open()

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (healthy)."""
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing fast)."""
        return self.state == CircuitState.OPEN

    def _transition_to_half_open(self) -> None:
        """Transition from OPEN to HALF_OPEN state."""
        logger.info(
            "Circuit breaker transitioning to half-open", provider=self.provider_name
        )
        self._state = CircuitState.HALF_OPEN
        self._half_open_call_count = 0
        self._success_count = 0

    def _transition_to_open(self) -> None:
        """Transition to OPEN state."""
        logger.warning(
            "Circuit breaker opening after failures",
            provider=self.provider_name,
            failure_count=self._failure_count,
        )
        self._state = CircuitState.OPEN
        self._last_failure_time = time.monotonic()

    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state (recovered)."""
        logger.info("Circuit breaker closing (recovered)", provider=self.provider_name)
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_call_count = 0

    def check(self) -> None:
        """Check if a request can proceed.

        Raises:
            CircuitBreakerOpenError: If circuit is open.
        """
        self.refresh_state()
        current_state = self.state

        if current_state == CircuitState.OPEN:
            cooldown_remaining = 0.0
            if self._last_failure_time is not None:
                elapsed = time.monotonic() - self._last_failure_time
                cooldown_remaining = max(0.0, self.config.cooldown_seconds - elapsed)

            raise CircuitBreakerOpenError(
                f"Circuit breaker is open for {self.provider_name}. "
                f"Too many consecutive failures. "
                f"Retry in {cooldown_remaining:.1f}s.",
                cooldown_remaining_seconds=cooldown_remaining,
                provider=self.provider_name,
            )

        if current_state == CircuitState.HALF_OPEN:
            if self._half_open_call_count >= self.config.half_open_max_calls:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker half-open call limit reached for "
                    f"{self.provider_name}. Waiting for pending calls to complete.",
                    cooldown_remaining_seconds=0.0,
                    provider=self.provider_name,
                )
            self._half_open_call_count += 1

    def record_success(self) -> None:
        """Record a successful API call."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.config.success_threshold:
                self._transition_to_closed()
        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed API call."""
        if self._state == CircuitState.HALF_OPEN:
            # Any failure in half-open reopens the circuit
            logger.warning(
                "Failure in half-open state, reopening circuit",
                provider=self.provider_name,
            )
            self._transition_to_open()
        elif self._state == CircuitState.CLOSED:
            self._failure_count += 1
            if self._failure_count >= self.config.failure_threshold:
                self._transition_to_open()

    def reset(self) -> None:
        """Reset the circuit breaker to initial state.

        Useful for testing or manual intervention.
        """
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._half_open_call_count = 0
        logger.info("Circuit breaker reset", provider=self.provider_name)
