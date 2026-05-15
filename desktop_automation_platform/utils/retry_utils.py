"""
Retry utilities for the Desktop Automation Platform.

Provides a configurable retry decorator and a programmatic retry loop
used by the execution engine and individual adapters.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any, TypeVar

from desktop_automation_platform.utils.logger import get_logger

_log = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class RetryConfig:
    """Immutable retry configuration record."""

    __slots__ = ("max_attempts", "delay_seconds", "backoff_factor", "reraise_on")

    def __init__(
        self,
        max_attempts: int = 3,
        delay_seconds: float = 0.5,
        backoff_factor: float = 1.0,
        reraise_on: tuple[type[Exception], ...] = (),
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self.max_attempts = max_attempts
        self.delay_seconds = delay_seconds
        self.backoff_factor = backoff_factor
        # Exceptions that bypass retry and propagate immediately
        self.reraise_on = reraise_on


def retry(
    max_attempts: int = 3,
    delay_seconds: float = 0.5,
    backoff_factor: float = 1.0,
    reraise_on: tuple[type[Exception], ...] = (),
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """
    Decorator that retries a function on failure.

    Parameters
    ----------
    max_attempts:
        Maximum total call attempts (1 = no retry).
    delay_seconds:
        Initial wait between attempts.
    backoff_factor:
        Multiply delay by this factor on each subsequent attempt.
        1.0 = constant delay.  2.0 = exponential back-off.
    reraise_on:
        Exception types that bypass retry and propagate immediately.
    exceptions:
        Exception types that trigger a retry (default: all exceptions).

    Example::

        @retry(max_attempts=3, delay_seconds=1.0, backoff_factor=2.0)
        def click_button():
            adapter.click(locator, session)
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return retry_call(
                fn,
                args=args,
                kwargs=kwargs,
                config=RetryConfig(
                    max_attempts=max_attempts,
                    delay_seconds=delay_seconds,
                    backoff_factor=backoff_factor,
                    reraise_on=reraise_on,
                ),
                exceptions=exceptions,
            )

        return wrapper  # type: ignore[return-value]

    return decorator


def retry_call(
    fn: Callable[..., Any],
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
    config: RetryConfig | None = None,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Any:
    """
    Execute ``fn(*args, **kwargs)`` with retry semantics.

    Returns the return value of the first successful call.
    Raises the last exception if all attempts fail.
    """
    cfg = config or RetryConfig()
    kw = kwargs or {}
    delay = cfg.delay_seconds
    last_exc: Exception | None = None

    for attempt in range(1, cfg.max_attempts + 1):
        try:
            return fn(*args, **kw)
        except cfg.reraise_on:
            raise
        except exceptions as exc:
            last_exc = exc
            if attempt < cfg.max_attempts:
                _log.debug(
                    "retry_scheduled",
                    fn=getattr(fn, "__name__", repr(fn)),
                    attempt=attempt,
                    max_attempts=cfg.max_attempts,
                    delay_seconds=delay,
                    error=str(exc),
                )
                time.sleep(delay)
                delay *= cfg.backoff_factor
            else:
                _log.warning(
                    "retry_exhausted",
                    fn=getattr(fn, "__name__", repr(fn)),
                    max_attempts=cfg.max_attempts,
                    error=str(exc),
                )

    # Should never be None if max_attempts >= 1 and an exception was raised
    assert last_exc is not None
    raise last_exc


def wait_until(
    condition: Callable[[], bool],
    timeout_seconds: float,
    poll_interval_seconds: float = 0.5,
    message: str = "Condition not met within timeout",
) -> bool:
    """
    Poll ``condition()`` until it returns True or ``timeout_seconds`` elapses.

    Returns True if the condition was met, False on timeout.
    Never raises — callers decide how to handle timeout.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            if condition():
                return True
        except Exception:
            pass
        time.sleep(poll_interval_seconds)
    return False
