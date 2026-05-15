"""
Unit tests for AdapterRegistry and AdapterManager.

All tests use mock adapters — no live desktop applications required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from desktop_automation_platform.adapters.adapter_manager import AdapterManager
from desktop_automation_platform.adapters.adapter_registry import AdapterRegistry
from desktop_automation_platform.config.schema import (
    AdapterMode,
    ApplicationConfig,
    FrameworkConfig,
    PlatformConfig,
)
from desktop_automation_platform.core.exceptions import AdapterNotAvailableException
from desktop_automation_platform.core.models import (
    AdapterType,
    ApplicationInfo,
    ApplicationSession,
    ApplicationTechnology,
    DetectionResult,
    SessionState,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_config(adapter_mode: AdapterMode = AdapterMode.AUTO) -> PlatformConfig:
    return PlatformConfig(
        framework=FrameworkConfig(
            adapter_mode=adapter_mode,
            detection_confidence_threshold=0.6,
        ),
        application=ApplicationConfig(name="Test App"),
    )


def _make_mock_adapter(
    adapter_type: AdapterType = AdapterType.FLAUI,
    available: bool = True,
    technologies: list[ApplicationTechnology] | None = None,
) -> MagicMock:
    adapter = MagicMock()
    adapter.adapter_type = adapter_type
    adapter.is_available.return_value = available
    adapter.supported_technologies = technologies or [ApplicationTechnology.WPF]
    return adapter


@pytest.fixture
def registry() -> AdapterRegistry:
    return AdapterRegistry()


@pytest.fixture
def mock_detector() -> MagicMock:
    detector = MagicMock()
    detector.detect_by_pid.return_value = DetectionResult(
        technology=ApplicationTechnology.WPF,
        confidence=0.9,
        recommended_adapter=AdapterType.FLAUI,
        evidence=["PresentationCore.dll loaded"],
    )
    detector.detect_by_executable.return_value = DetectionResult(
        technology=ApplicationTechnology.WPF,
        confidence=0.7,
        recommended_adapter=AdapterType.FLAUI,
        evidence=["mscoree.dll import"],
    )
    return detector


@pytest.fixture
def manager(
    registry: AdapterRegistry, mock_detector: MagicMock
) -> AdapterManager:
    config = _make_config()
    return AdapterManager(registry=registry, detector=mock_detector, config=config)


# ---------------------------------------------------------------------------
# AdapterRegistry tests
# ---------------------------------------------------------------------------


class TestAdapterRegistry:
    def test_register_and_get(self, registry: AdapterRegistry) -> None:
        mock = _make_mock_adapter()
        registry.register(
            adapter_type=AdapterType.FLAUI,
            factory=lambda: mock,
            supported_technologies=[ApplicationTechnology.WPF],
            check_availability=False,
        )
        reg = registry.get(AdapterType.FLAUI)
        assert reg is not None
        assert reg.adapter_type == AdapterType.FLAUI

    def test_get_or_raise_unregistered(self, registry: AdapterRegistry) -> None:
        with pytest.raises(AdapterNotAvailableException):
            registry.get_or_raise(AdapterType.FLAUI)

    def test_get_or_raise_unavailable(self, registry: AdapterRegistry) -> None:
        mock = _make_mock_adapter(available=False)
        registry.register(
            adapter_type=AdapterType.FLAUI,
            factory=lambda: mock,
            supported_technologies=[ApplicationTechnology.WPF],
            check_availability=True,
        )
        with pytest.raises(AdapterNotAvailableException):
            registry.get_or_raise(AdapterType.FLAUI)

    def test_find_for_technology_returns_priority_order(
        self, registry: AdapterRegistry
    ) -> None:
        flaui = _make_mock_adapter(AdapterType.FLAUI, technologies=[ApplicationTechnology.WPF])
        pywinauto = _make_mock_adapter(
            AdapterType.PYWINAUTO, technologies=[ApplicationTechnology.WPF]
        )
        registry.register(
            AdapterType.PYWINAUTO,
            lambda: pywinauto,
            [ApplicationTechnology.WPF],
            check_availability=False,
        )
        registry.register(
            AdapterType.FLAUI,
            lambda: flaui,
            [ApplicationTechnology.WPF],
            check_availability=False,
        )
        results = registry.find_for_technology(ApplicationTechnology.WPF)
        # FlaUI should be first (priority=1), pywinauto second (priority=2)
        assert results[0].adapter_type == AdapterType.FLAUI
        assert results[1].adapter_type == AdapterType.PYWINAUTO

    def test_find_for_technology_excludes_unavailable(
        self, registry: AdapterRegistry
    ) -> None:
        mock = _make_mock_adapter(available=False)
        registry.register(
            AdapterType.FLAUI,
            lambda: mock,
            [ApplicationTechnology.WPF],
            check_availability=True,
        )
        results = registry.find_for_technology(ApplicationTechnology.WPF)
        assert results == []

    def test_all_available_filters_unavailable(self, registry: AdapterRegistry) -> None:
        available = _make_mock_adapter(AdapterType.FLAUI, available=True)
        unavailable = _make_mock_adapter(AdapterType.PYWINAUTO, available=False)
        registry.register(
            AdapterType.FLAUI, lambda: available, [ApplicationTechnology.WPF], False
        )
        registry.register(
            AdapterType.PYWINAUTO, lambda: unavailable, [ApplicationTechnology.WIN32], False
        )
        # Manually mark PYWINAUTO as unavailable (since check_availability=False)
        registry._registrations[AdapterType.PYWINAUTO].available = False
        results = registry.all_available()
        assert all(r.available for r in results)

    def test_unregister(self, registry: AdapterRegistry) -> None:
        mock = _make_mock_adapter()
        registry.register(AdapterType.FLAUI, lambda: mock, [], False)
        assert registry.is_registered(AdapterType.FLAUI)
        registry.unregister(AdapterType.FLAUI)
        assert not registry.is_registered(AdapterType.FLAUI)

    def test_diagnostic_report_returns_string(self, registry: AdapterRegistry) -> None:
        mock = _make_mock_adapter()
        registry.register(AdapterType.FLAUI, lambda: mock, [ApplicationTechnology.WPF], False)
        report = registry.diagnostic_report()
        assert "flaui" in report.lower()
        assert "wpf" in report.lower()


# ---------------------------------------------------------------------------
# AdapterManager tests
# ---------------------------------------------------------------------------


class TestAdapterManager:
    def _register_flaui(self, registry: AdapterRegistry) -> MagicMock:
        mock = _make_mock_adapter(AdapterType.FLAUI, technologies=[ApplicationTechnology.WPF])
        registry.register(
            AdapterType.FLAUI,
            lambda: mock,
            [ApplicationTechnology.WPF],
            check_availability=False,
        )
        return mock

    def test_resolve_adapter_with_explicit_mode(
        self, registry: AdapterRegistry, mock_detector: MagicMock
    ) -> None:
        self._register_flaui(registry)
        config = _make_config(adapter_mode=AdapterMode.FLAUI)
        manager = AdapterManager(registry=registry, detector=mock_detector, config=config)
        app_info = ApplicationInfo(name="Test")
        adapter = manager.resolve_adapter(app_info)
        assert adapter.adapter_type == AdapterType.FLAUI
        mock_detector.detect_by_pid.assert_not_called()

    def test_resolve_adapter_auto_uses_detection(
        self,
        registry: AdapterRegistry,
        mock_detector: MagicMock,
        manager: AdapterManager,
    ) -> None:
        self._register_flaui(registry)
        app_info = ApplicationInfo(name="Test", process_id=1234)
        adapter = manager.resolve_adapter(app_info)
        assert adapter.adapter_type == AdapterType.FLAUI
        mock_detector.detect_by_pid.assert_called_once_with(1234)

    def test_resolve_uses_technology_from_app_info(
        self, registry: AdapterRegistry, mock_detector: MagicMock
    ) -> None:
        self._register_flaui(registry)
        config = _make_config()
        manager = AdapterManager(registry=registry, detector=mock_detector, config=config)
        app_info = ApplicationInfo(name="Test", technology=ApplicationTechnology.WPF)
        adapter = manager.resolve_adapter(app_info)
        assert adapter.adapter_type == AdapterType.FLAUI
        # Should not call detector when technology is already known
        mock_detector.detect_by_pid.assert_not_called()

    def test_get_adapter_for_session_caches(
        self, registry: AdapterRegistry, mock_detector: MagicMock
    ) -> None:
        self._register_flaui(registry)
        config = _make_config()
        manager = AdapterManager(registry=registry, detector=mock_detector, config=config)
        session = ApplicationSession(
            app_info=ApplicationInfo(name="Test", technology=ApplicationTechnology.WPF),
            adapter_type=AdapterType.FLAUI,
            state=SessionState.ACTIVE,
        )
        session.mark_active()
        adapter1 = manager.get_adapter_for_session(session)
        adapter2 = manager.get_adapter_for_session(session)
        assert adapter1 is adapter2

    def test_release_session_clears_cache(
        self,
        registry: AdapterRegistry,
        mock_detector: MagicMock,
    ) -> None:
        self._register_flaui(registry)
        config = _make_config()
        manager = AdapterManager(registry=registry, detector=mock_detector, config=config)
        session = ApplicationSession(
            app_info=ApplicationInfo(name="Test", technology=ApplicationTechnology.WPF),
            state=SessionState.ACTIVE,
        )
        session.mark_active()
        manager.get_adapter_for_session(session)
        assert session.session_id in manager._session_adapters
        manager.release_session(session)
        assert session.session_id not in manager._session_adapters

    def test_no_available_adapter_raises(
        self, registry: AdapterRegistry, mock_detector: MagicMock
    ) -> None:
        manager = AdapterManager(
            registry=registry, detector=mock_detector, config=_make_config()
        )
        session = ApplicationSession(
            app_info=ApplicationInfo(name="Test"),
            state=SessionState.ACTIVE,
        )
        session.mark_active()
        with pytest.raises(AdapterNotAvailableException):
            manager.get_adapter_for_session(session)

    def test_low_confidence_detection_falls_back(
        self, registry: AdapterRegistry
    ) -> None:
        self._register_flaui(registry)
        detector = MagicMock()
        detector.detect_by_pid.return_value = DetectionResult(
            technology=ApplicationTechnology.WPF,
            confidence=0.2,  # Below threshold
            recommended_adapter=AdapterType.FLAUI,
            evidence=[],
        )
        config = _make_config()
        manager = AdapterManager(registry=registry, detector=detector, config=config)
        app_info = ApplicationInfo(name="Test", process_id=999)
        # Should fall back to first available (FlaUI) even with low confidence
        adapter = manager.resolve_adapter(app_info)
        assert adapter is not None

    def test_diagnostic_report_contains_adapter_info(
        self, registry: AdapterRegistry, mock_detector: MagicMock
    ) -> None:
        self._register_flaui(registry)
        manager = AdapterManager(
            registry=registry, detector=mock_detector, config=_make_config()
        )
        report = manager.diagnostic_report()
        assert "flaui" in report.lower()
