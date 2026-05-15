"""
AdapterManager — orchestrates adapter selection, lifecycle, and fallback.

Responsibilities
----------------
1. Select the optimal adapter for an application session based on:
   a. Explicit ``adapter_mode`` in framework config, OR
   b. Automated technology detection via IApplicationDetector
2. Instantiate and return the adapter via the registry factory
3. Manage a per-session adapter instance cache
4. Handle adapter-level fallback when the primary adapter fails
5. Surface diagnostics for observability

This is the single point of contact between the execution engine and the
adapter layer — nothing else should instantiate adapters directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_automation_platform.adapters.adapter_registry import AdapterRegistry
from desktop_automation_platform.core.exceptions import (
    AdapterNotAvailableException,
    ApplicationNotFoundException,
)
from desktop_automation_platform.core.interfaces.application_adapter import IApplicationAdapter
from desktop_automation_platform.core.interfaces.application_detector import IApplicationDetector
from desktop_automation_platform.core.models import (
    AdapterType,
    ApplicationInfo,
    ApplicationSession,
    ApplicationTechnology,
    DetectionResult,
)
from desktop_automation_platform.utils.logger import get_logger

if TYPE_CHECKING:
    from desktop_automation_platform.config.schema import AdapterMode, PlatformConfig

_log = get_logger(__name__)


class AdapterManager:
    """
    Resolves and caches adapter instances for active automation sessions.

    Usage::

        manager = AdapterManager(registry, detector, config)
        adapter = manager.get_adapter_for_session(session)
        result  = adapter.click(locator, session)
    """

    def __init__(
        self,
        registry: AdapterRegistry,
        detector: IApplicationDetector,
        config: "PlatformConfig",
    ) -> None:
        self._registry = registry
        self._detector = detector
        self._config = config
        # session_id → adapter instance (avoids re-selecting on every call)
        self._session_adapters: dict[str, IApplicationAdapter] = {}

    # ------------------------------------------------------------------
    # Primary API
    # ------------------------------------------------------------------

    def get_adapter_for_session(
        self,
        session: ApplicationSession,
    ) -> IApplicationAdapter:
        """
        Return the adapter assigned to ``session``.

        If the session already has an assigned adapter it is returned from
        cache. Otherwise adapter selection is performed and the result is
        cached.
        """
        if session.session_id in self._session_adapters:
            return self._session_adapters[session.session_id]

        adapter = self._select_adapter(session)
        self._session_adapters[session.session_id] = adapter
        _log.info(
            "adapter_assigned",
            session_id=session.session_id,
            adapter_type=adapter.adapter_type.value,
        )
        return adapter

    def resolve_adapter(
        self,
        app_info: ApplicationInfo,
    ) -> IApplicationAdapter:
        """
        Select the best adapter for ``app_info`` without creating a session.
        Used by the keyword layer's ``Launch Application`` implementation.
        """
        adapter_type = self._resolve_adapter_type(app_info)

        if adapter_type is None:
            available = self._registry.all_available()
            if not available:
                raise AdapterNotAvailableException(
                    adapter_type="any",
                    reason=(
                        "Technology detection returned no confident match and no adapters "
                        "are available. For Windows apps, run "
                        ".\\scripts\\setup_flaui.ps1 to install FlaUI, or set "
                        "adapter_mode: flaui in config.yaml to select it explicitly."
                    ),
                )
            adapter_type = available[0].adapter_type
            _log.warning(
                "adapter_fallback_to_first_available",
                adapter_type=adapter_type.value,
            )

        return self._instantiate(adapter_type)

    def release_session(self, session: ApplicationSession) -> None:
        """Remove the adapter cache entry for a closed session."""
        self._session_adapters.pop(session.session_id, None)

    def get_detection_result(self, app_info: ApplicationInfo) -> DetectionResult | None:
        """
        Run technology detection for ``app_info`` and return the result.
        Returns None when detection cannot be performed (no PID, no exe).
        """
        if app_info.process_id is not None:
            try:
                return self._detector.detect_by_pid(app_info.process_id)
            except (ApplicationNotFoundException, Exception) as exc:
                _log.warning("detection_by_pid_failed", pid=app_info.process_id, error=str(exc))
        if app_info.executable is not None:
            try:
                return self._detector.detect_by_executable(app_info.executable)
            except (ApplicationNotFoundException, Exception) as exc:
                _log.warning(
                    "detection_by_exe_failed",
                    executable=app_info.executable,
                    error=str(exc),
                )
        return None

    def diagnostic_report(self) -> str:
        """Return combined registry + active session diagnostics."""
        lines = [
            self._registry.diagnostic_report(),
            "",
            f"Active sessions: {len(self._session_adapters)}",
        ]
        for sid, adapter in self._session_adapters.items():
            lines.append(f"  {sid[:8]}...  adapter={adapter.adapter_type.value}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Private — adapter selection logic
    # ------------------------------------------------------------------

    def _select_adapter(self, session: ApplicationSession) -> IApplicationAdapter:
        """Full adapter selection pipeline for a new session."""
        app_info = session.app_info
        adapter_type = self._resolve_adapter_type(app_info) if app_info else None

        if adapter_type is None:
            # Last resort: pick the first available adapter
            available = self._registry.all_available()
            if not available:
                raise AdapterNotAvailableException(
                    adapter_type="any",
                    reason="No adapters are registered and available.",
                )
            adapter_type = available[0].adapter_type
            _log.warning(
                "adapter_fallback_to_first_available",
                adapter_type=adapter_type.value,
                session_id=session.session_id,
            )

        return self._instantiate(adapter_type)

    def _resolve_adapter_type(self, app_info: ApplicationInfo | None) -> AdapterType | None:
        """
        Determine the correct AdapterType using config, detection, and technology mapping.

        Priority:
        1. Explicit ``adapter_mode`` in config (if not AUTO)
        2. ``app_info.technology`` (if set and not UNKNOWN)
        3. Runtime detection (by PID or executable)
        4. None → caller handles fallback
        """
        from desktop_automation_platform.config.schema import AdapterMode

        mode = self._config.framework.adapter_mode

        # 1. Explicit mode
        if mode != AdapterMode.AUTO:
            return AdapterType(mode.value)

        # 2. Pre-set technology on app_info
        if app_info and app_info.technology and app_info.technology != ApplicationTechnology.UNKNOWN:
            return self._technology_to_adapter(app_info.technology)

        # 3. Runtime detection
        if app_info:
            result = self.get_detection_result(app_info)
            if result and result.confidence >= self._config.framework.detection_confidence_threshold:
                _log.info(
                    "technology_detected",
                    technology=result.technology.value,
                    confidence=result.confidence,
                    recommended_adapter=result.recommended_adapter.value,
                    evidence=result.evidence,
                )
                return result.recommended_adapter
            elif result:
                _log.warning(
                    "detection_confidence_below_threshold",
                    technology=result.technology.value,
                    confidence=result.confidence,
                    threshold=self._config.framework.detection_confidence_threshold,
                )

        return None

    def _technology_to_adapter(self, technology: ApplicationTechnology) -> AdapterType:
        """Map a detected technology to the highest-priority available adapter."""
        candidates = self._registry.find_for_technology(technology)
        if candidates:
            return candidates[0].adapter_type

        # No registered adapter for this technology — fall back to FlaUI for .NET apps
        _log.warning(
            "no_adapter_for_technology",
            technology=technology.value,
            fallback=AdapterType.FLAUI.value,
        )
        return AdapterType.FLAUI

    def _instantiate(self, adapter_type: AdapterType) -> IApplicationAdapter:
        """Instantiate an adapter from the registry factory."""
        registration = self._registry.get_or_raise(adapter_type)
        try:
            instance = registration.factory()
            _log.debug("adapter_instantiated", adapter_type=adapter_type.value)
            return instance
        except Exception as exc:
            raise AdapterNotAvailableException(
                adapter_type=adapter_type.value,
                reason=f"Factory raised during instantiation: {exc}",
            ) from exc
