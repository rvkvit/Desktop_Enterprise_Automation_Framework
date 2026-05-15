"""
IExecutionEngine — orchestrates keyword execution with retry and recovery.

The execution engine sits between the Robot Framework keyword layer and the
adapter layer. It owns retry logic, timeout enforcement, and coordinates
with the recovery engine on failure.

This separation keeps both the keyword layer and the adapters free of
orchestration concerns.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

from desktop_automation_platform.core.models import (
    ActionResult,
    ApplicationSession,
    UnifiedLocator,
)


class IExecutionEngine(ABC):
    """
    Executes automation actions against a session with configurable retry,
    timeout, and recovery.
    """

    @abstractmethod
    def execute(
        self,
        action_name: str,
        action_fn: Callable[..., Any],
        session: ApplicationSession,
        locator: UnifiedLocator | None = None,
        timeout: float | None = None,
        retry_count: int | None = None,
        **kwargs: Any,
    ) -> ActionResult:
        """
        Execute ``action_fn`` with retry and recovery.

        Parameters
        ----------
        action_name:
            Human-readable name used in logs and reports (e.g. ``"click"``)
        action_fn:
            Zero-argument callable that performs the native automation step.
            The execution engine is responsible for retrying it.
        session:
            Active automation session.
        locator:
            Unified locator being resolved (for diagnostics / fallback logic).
        timeout:
            Per-action timeout override; falls back to framework config.
        retry_count:
            Retry override; falls back to framework config.
        kwargs:
            Passed through to ``action_fn``.
        """
        ...

    @abstractmethod
    def execute_with_locator_fallback(
        self,
        action_name: str,
        action_fn_factory: Callable[[Any], Callable[[], Any]],
        locator: UnifiedLocator,
        session: ApplicationSession,
        timeout: float | None = None,
    ) -> ActionResult:
        """
        Execute with explicit locator fallback chain iteration.

        ``action_fn_factory`` receives a translated native locator and must
        return a zero-argument callable that performs the action with that
        locator. The engine iterates through ``locator.all_strategies()``
        until one succeeds or all fail.
        """
        ...

    @abstractmethod
    def set_default_timeout(self, timeout_seconds: float) -> None:
        """Override the framework-wide default timeout for this engine instance."""
        ...

    @abstractmethod
    def set_retry_count(self, count: int) -> None:
        """Override the framework-wide retry count for this engine instance."""
        ...
