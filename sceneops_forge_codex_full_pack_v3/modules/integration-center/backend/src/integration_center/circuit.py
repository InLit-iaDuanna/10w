"""Transient-failure circuit breaker for typed integration probes."""

import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

from .schemas import CircuitSnapshot, CircuitState


class CircuitOpenError(RuntimeError):
    def __init__(self, retry_at: datetime) -> None:
        super().__init__("integration circuit is open")
        self.retry_at = retry_at


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, cooldown: timedelta = timedelta(seconds=30)) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be positive")
        if cooldown.total_seconds() <= 0:
            raise ValueError("cooldown must be positive")
        self._failure_threshold = failure_threshold
        self._cooldown = cooldown
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at: Optional[datetime] = None
        self._half_open_probe_in_flight = False
        self._lock = threading.RLock()

    def before_call(self, now: datetime) -> None:
        with self._lock:
            if self._state == CircuitState.OPEN:
                retry_at = self._retry_at()
                if now < retry_at:
                    raise CircuitOpenError(retry_at)
                self._state = CircuitState.HALF_OPEN
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_probe_in_flight:
                    raise CircuitOpenError(self._retry_at())
                self._half_open_probe_in_flight = True

    def record_success(self) -> None:
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failures = 0
            self._opened_at = None
            self._half_open_probe_in_flight = False

    def record_failure(self, now: datetime, transient: bool) -> None:
        with self._lock:
            self._half_open_probe_in_flight = False
            if not transient:
                self._state = CircuitState.CLOSED
                self._failures = 0
                self._opened_at = None
                return
            self._failures += 1
            if self._state == CircuitState.HALF_OPEN or self._failures >= self._failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = now

    def snapshot(self) -> CircuitSnapshot:
        with self._lock:
            return CircuitSnapshot(
                state=self._state,
                consecutive_failures=self._failures,
                opened_at=self._opened_at,
                retry_at=self._retry_at() if self._opened_at is not None else None,
            )

    def _retry_at(self) -> datetime:
        return (self._opened_at or datetime.now(timezone.utc)) + self._cooldown
