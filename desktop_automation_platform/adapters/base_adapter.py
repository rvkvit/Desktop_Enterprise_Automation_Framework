"""
BaseDesktopAdapter — abstract base class for all concrete adapters.

Provides:
- Structured action timing and logging
- Screenshot-on-failure capture coordination
- Locator fallback iteration
- Common session validation guard
- ActionResult construction helpers

Concrete adapters extend this class and implement the abstract native methods
(``_native_click``, ``_native_input_text``, etc.) without worrying about
retry, timing, or logging — that stays here.
"""

from __future__ import annotations

import time
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Callable

from desktop_automation_platform.core.interfaces.application_adapter import IApplicationAdapter
from desktop_automation_platform.core.models import (
    ActionResult,
    ActionStatus,
    ApplicationSession,
    LocatorDefinition,
    SessionState,
    UnifiedLocator,
)
from desktop_automation_platform.utils.logger import get_logger

if TYPE_CHECKING:
    from desktop_automation_platform.config.schema import PlatformConfig
    from desktop_automation_platform.core.interfaces.screenshot_manager import IScreenshotManager

_log = get_logger(__name__)


class BaseDesktopAdapter(IApplicationAdapter):
    """
    Shared adapter scaffolding. Subclasses implement ``_native_*`` methods;
    this class owns the execution contract.
    """

    def __init__(
        self,
        config: "PlatformConfig",
        screenshot_manager: "IScreenshotManager",
    ) -> None:
        self._config = config
        self._screenshot_manager = screenshot_manager
        # Subclasses set this to enable self-healing (Phase 5)
        self._recovery_manager: Any = None

    # ------------------------------------------------------------------
    # Session guard
    # ------------------------------------------------------------------

    def _assert_session_active(self, session: ApplicationSession) -> None:
        """Raise SessionNotActiveException if the session is not ACTIVE."""
        from desktop_automation_platform.core.exceptions import SessionNotActiveException

        if not session.is_active():
            raise SessionNotActiveException(
                session_id=session.session_id,
                current_state=session.state.value,
            )

    # ------------------------------------------------------------------
    # Timed action executor
    # ------------------------------------------------------------------

    def _execute_action(
        self,
        action_name: str,
        native_fn: Callable[[], Any],
        session: ApplicationSession,
        locator: UnifiedLocator | None = None,
        locator_used: LocatorDefinition | None = None,
        locator_attempts: list[LocatorDefinition] | None = None,
    ) -> ActionResult:
        """
        Execute ``native_fn`` and wrap the outcome in an ``ActionResult``.

        Captures a screenshot on failure if configured.
        Never raises — caller inspects ActionResult.status.
        """
        self._assert_session_active(session)
        start = time.monotonic()

        try:
            native_fn()
            duration_ms = (time.monotonic() - start) * 1000
            result = ActionResult(
                action=action_name,
                status=ActionStatus.SUCCESS,
                duration_ms=duration_ms,
                locator_used=locator_used,
                locator_attempts=locator_attempts or [],
            )
            _log.info(
                "action_succeeded",
                action=action_name,
                duration_ms=round(duration_ms, 2),
                adapter=self.adapter_type.value,
                session_id=session.session_id,
            )
            return result
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            screenshot_path: str | None = None
            if self._config.framework.screenshot_on_failure:
                screenshot_path = self._screenshot_manager.capture_on_failure(
                    session=session,
                    action_name=action_name,
                )
            _log.error(
                "action_failed",
                action=action_name,
                duration_ms=round(duration_ms, 2),
                adapter=self.adapter_type.value,
                session_id=session.session_id,
                error=str(exc),
                screenshot=screenshot_path,
            )
            return ActionResult(
                action=action_name,
                status=ActionStatus.FAILED,
                duration_ms=duration_ms,
                locator_used=locator_used,
                locator_attempts=locator_attempts or [],
                error_message=str(exc),
                screenshot_path=screenshot_path,
            )

    def _execute_with_fallback(
        self,
        action_name: str,
        native_fn_factory: Callable[[LocatorDefinition], Callable[[], Any]],
        locator: UnifiedLocator,
        session: ApplicationSession,
    ) -> ActionResult:
        """
        Try each strategy in ``locator.all_strategies()`` in order.

        ``native_fn_factory`` receives a ``LocatorDefinition`` and returns
        a zero-arg callable that performs the native action with that locator.

        Returns the first successful ``ActionResult``, or the last failure
        result if all strategies are exhausted.
        """
        strategies = locator.all_strategies()
        timeout_override = locator.primary.timeout or self._config.execution.timeout
        attempts: list[LocatorDefinition] = []
        last_result: ActionResult | None = None

        primary_strategy = strategies[0].strategy.value if strategies else "unknown"

        for loc_def in strategies:
            attempts.append(loc_def)
            _log.debug(
                "locator_strategy_attempt",
                locator=locator.name,
                strategy=loc_def.strategy.value,
                value=loc_def.value,
                attempt=len(attempts),
                total=len(strategies),
            )
            native_fn = native_fn_factory(loc_def)
            result = self._execute_action(
                action_name=action_name,
                native_fn=native_fn,
                session=session,
                locator=locator,
                locator_used=loc_def,
                locator_attempts=list(attempts),
            )
            if result.is_success():
                if len(attempts) > 1:
                    _log.info(
                        "fallback_locator_succeeded",
                        locator=locator.name,
                        strategy=loc_def.strategy.value,
                        fallback_index=len(attempts) - 1,
                    )
                    # Record soft-heal event in the healing tracker
                    if self._recovery_manager is not None:
                        self._recovery_manager.record_fallback_heal(
                            locator_name=locator.name,
                            failed_strategy=primary_strategy,
                            healed_by=loc_def.strategy.value,
                        )
                return result
            last_result = result

        # All strategies exhausted — attempt hard recovery if available
        assert last_result is not None
        if self._recovery_manager is not None:
            native_ctx = self._get_recovery_native_context(session)
            primary_loc = strategies[0]

            def _retry() -> bool:
                try:
                    native_fn_factory(primary_loc)()
                    return True
                except Exception:
                    return False

            recovered = self._recovery_manager.attempt_recovery(
                locator=locator,
                session=session,
                retry_fn=_retry,
                failed_strategy=primary_strategy,
                native_context=native_ctx,
            )
            if recovered:
                return self._execute_action(
                    action_name=action_name,
                    native_fn=native_fn_factory(primary_loc),
                    session=session,
                    locator=locator,
                    locator_used=primary_loc,
                    locator_attempts=list(attempts),
                )

        last_result.locator_attempts = attempts
        last_result.status = ActionStatus.ELEMENT_NOT_FOUND
        return last_result

    def _get_recovery_native_context(self, session: ApplicationSession) -> dict:
        """Return adapter-specific context dict for recovery strategies.
        Subclasses override this to expose their native objects."""
        return {}

    # ------------------------------------------------------------------
    # Default window management (delegates to native; adapters may override)
    # ------------------------------------------------------------------

    def maximize_window(
        self,
        session: ApplicationSession,
        window_title: str | None = None,
    ) -> ActionResult:
        return self._execute_action(
            action_name="maximize_window",
            native_fn=lambda: self._native_maximize_window(session, window_title),
            session=session,
        )

    def minimize_window(
        self,
        session: ApplicationSession,
        window_title: str | None = None,
    ) -> ActionResult:
        return self._execute_action(
            action_name="minimize_window",
            native_fn=lambda: self._native_minimize_window(session, window_title),
            session=session,
        )

    # ------------------------------------------------------------------
    # Abstract native methods — adapters implement these
    # ------------------------------------------------------------------

    @abstractmethod
    def _native_maximize_window(
        self,
        session: ApplicationSession,
        window_title: str | None,
    ) -> None: ...

    @abstractmethod
    def _native_minimize_window(
        self,
        session: ApplicationSession,
        window_title: str | None,
    ) -> None: ...
