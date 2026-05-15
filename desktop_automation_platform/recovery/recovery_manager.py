"""
RecoveryManager — orchestrates recovery strategies when an element action fails.

Called by the base adapter after all locator fallbacks are exhausted.
Tries each registered IRecoveryStrategy in priority order; the first
strategy that succeeds causes the original action to be retried once.

Recovery flow
-------------
    element lookup (primary) → FAIL
    element lookup (fallback 1..n) → all FAIL
    RecoveryManager.attempt_recovery() →
        strategy 1: popup_dismissal  → try, if cleared retry element lookup
        strategy 2: stale_window     → try, if re-attached retry element lookup
        strategy 3: fuzzy_match      → try, if found retry element lookup
    still FAIL → raise ElementNotFoundException

All healing events are recorded in HealingTracker for end-of-suite reporting.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from desktop_automation_platform.core.models import ApplicationSession, UnifiedLocator
from desktop_automation_platform.recovery.healing_tracker import HealingTracker
from desktop_automation_platform.utils.logger import get_logger

_log = get_logger(__name__)


class RecoveryManager:
    """
    Pluggable recovery orchestrator.

    Adapters instantiate this once and call ``attempt_recovery`` when
    all locator strategies are exhausted.
    """

    def __init__(self) -> None:
        self._strategies: list[Any] = []  # list[IRecoveryStrategy]
        self._tracker = HealingTracker.instance()

    def register(self, strategy: Any) -> None:
        """Register a recovery strategy (IRecoveryStrategy implementor)."""
        self._strategies.append(strategy)

    def attempt_recovery(
        self,
        locator: UnifiedLocator,
        session: ApplicationSession,
        retry_fn: Callable[[], bool],
        failed_strategy: str,
        native_context: dict[str, Any] | None = None,
    ) -> bool:
        """
        Try each registered strategy in order.

        Parameters
        ----------
        locator:
            The locator that could not be found.
        session:
            Active application session.
        retry_fn:
            Zero-arg callable that returns True if the element is now
            findable (called after each strategy is applied).
        failed_strategy:
            The strategy name that failed — used in healing report.
        native_context:
            Adapter-specific context (e.g. FlaUI automation object).

        Returns
        -------
        bool
            True if any strategy succeeded and ``retry_fn`` returned True.
        """
        if not self._strategies:
            return False

        _log.debug(
            "recovery_manager_activating",
            locator=locator.name,
            strategies=[s.__class__.__name__ for s in self._strategies],
        )

        for strategy in self._strategies:
            strategy_name = strategy.__class__.__name__
            try:
                applied = strategy.apply(
                    locator=locator,
                    session=session,
                    native_context=native_context or {},
                )
                if not applied:
                    continue

                _log.debug("recovery_strategy_applied", strategy=strategy_name, locator=locator.name)

                # Give the UI a moment to settle after recovery
                time.sleep(0.5)

                if retry_fn():
                    _log.info(
                        "recovery_succeeded",
                        strategy=strategy_name,
                        locator=locator.name,
                    )
                    self._tracker.record_recovery(
                        locator_name=locator.name,
                        failed_strategy=failed_strategy,
                        heal_type=strategy.heal_type,
                        note=f"Recovered by {strategy_name}",
                    )
                    return True

            except Exception as exc:
                _log.debug(
                    "recovery_strategy_error",
                    strategy=strategy_name,
                    locator=locator.name,
                    error=str(exc),
                )

        _log.debug("recovery_manager_exhausted", locator=locator.name)
        return False

    def record_fallback_heal(
        self, locator_name: str, failed_strategy: str, healed_by: str
    ) -> None:
        """Called by the base adapter when a fallback locator succeeds."""
        self._tracker.record_fallback(
            locator_name=locator_name,
            failed_strategy=failed_strategy,
            healed_by=healed_by,
        )
