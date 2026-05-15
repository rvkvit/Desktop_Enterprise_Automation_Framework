"""
IRecoveryEngine — self-healing and exception recovery strategies.

When an action fails, the execution engine delegates to the recovery engine
which tries registered strategies in priority order until the session is
restored or all strategies are exhausted.

Recovery strategy catalogue (implementations in ``recovery/strategies/``):
- StaleWindowRecovery   — re-attaches after window handle goes stale
- PopupDismissalRecovery — closes unexpected dialog interruptions
- ApplicationRelaunchRecovery — kills and relaunches crashed applications
- SessionReconnectRecovery — reconnects RDP/Citrix sessions
- AdapterFallbackRecovery — switches to a secondary adapter on failure
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from desktop_automation_platform.core.models import RecoveryContext, RecoveryResult


class IRecoveryEngine(ABC):
    """Orchestrates recovery strategy selection and execution."""

    @abstractmethod
    def attempt_recovery(self, context: RecoveryContext) -> RecoveryResult:
        """
        Iterate through registered recovery strategies in priority order
        until one succeeds or all are exhausted.

        Returns a ``RecoveryResult`` regardless of outcome — never raises.
        Callers inspect ``RecoveryResult.recovered`` to decide whether to
        retry the original action or propagate failure.
        """
        ...

    @abstractmethod
    def register_strategy(
        self,
        strategy: "IRecoveryStrategy",
        priority: int = 100,
    ) -> None:
        """
        Register a recovery strategy.

        Lower ``priority`` values are tried first.
        Strategies with equal priority are tried in registration order.
        """
        ...

    @abstractmethod
    def clear_strategies(self) -> None:
        """Remove all registered strategies (primarily for testing)."""
        ...


class IRecoveryStrategy(ABC):
    """
    Single recovery strategy. Implement one responsibility per class.

    Strategies are stateless; all context is provided via ``RecoveryContext``.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique strategy name used in logs and reports."""
        ...

    @abstractmethod
    def can_handle(self, context: RecoveryContext) -> bool:
        """
        Return True if this strategy is applicable to the given failure context.
        Called before ``recover`` to avoid unnecessary attempts.
        """
        ...

    @abstractmethod
    def recover(self, context: RecoveryContext) -> RecoveryResult:
        """
        Attempt to restore the automation session.
        Must not raise; return a ``RecoveryResult`` with ``recovered=False``
        on failure.
        """
        ...
