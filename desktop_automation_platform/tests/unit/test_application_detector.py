"""
Unit tests for TechnologyClassifier and WindowsApplicationDetector.

ProcessInspector is mocked so these tests run on any OS without
requiring Windows admin privileges or live processes.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from desktop_automation_platform.adapters.detector.application_detector import (
    WindowsApplicationDetector,
)
from desktop_automation_platform.adapters.detector.technology_classifier import (
    ProcessSignals,
    TechnologyClassifier,
)
from desktop_automation_platform.core.exceptions import ApplicationNotFoundException
from desktop_automation_platform.core.models import AdapterType, ApplicationTechnology


# ---------------------------------------------------------------------------
# ProcessSignals helpers
# ---------------------------------------------------------------------------


def _signals(
    exe_name: str = "app.exe",
    modules: list[str] | None = None,
    window_classes: list[str] | None = None,
    is_dotnet: bool = False,
) -> ProcessSignals:
    return ProcessSignals(
        pid=1234,
        exe_name=exe_name,
        modules=[m.lower() for m in (modules or [])],
        window_class_names=window_classes or [],
        cmdline=[exe_name],
        is_dotnet=is_dotnet,
    )


# ---------------------------------------------------------------------------
# TechnologyClassifier tests
# ---------------------------------------------------------------------------


class TestTechnologyClassifier:
    @pytest.fixture
    def classifier(self) -> TechnologyClassifier:
        return TechnologyClassifier()

    def test_wpf_detection_by_modules(self, classifier: TechnologyClassifier) -> None:
        signals = _signals(
            modules=["PresentationCore.dll", "PresentationFramework.dll"],
            is_dotnet=True,
        )
        result = classifier.classify(signals)
        assert result.technology == ApplicationTechnology.WPF
        assert result.confidence >= 0.6
        assert result.recommended_adapter == AdapterType.FLAUI

    def test_wpf_detection_by_window_class(self, classifier: TechnologyClassifier) -> None:
        signals = _signals(
            window_classes=["HwndWrapper[MyApp;;]"],
            is_dotnet=True,
        )
        result = classifier.classify(signals)
        assert result.technology == ApplicationTechnology.WPF
        assert result.confidence >= 0.4

    def test_winforms_detection_by_modules(self, classifier: TechnologyClassifier) -> None:
        signals = _signals(
            modules=["System.Windows.Forms.dll"],
            is_dotnet=True,
        )
        result = classifier.classify(signals)
        assert result.technology == ApplicationTechnology.WINFORMS
        assert result.recommended_adapter == AdapterType.FLAUI

    def test_winforms_detection_by_window_class(self, classifier: TechnologyClassifier) -> None:
        signals = _signals(
            modules=["System.Windows.Forms.dll"],
            window_classes=["WindowsForms10.BUTTON.app.0.141b42a5"],
            is_dotnet=True,
        )
        result = classifier.classify(signals)
        assert result.technology == ApplicationTechnology.WINFORMS
        assert result.confidence >= 0.9

    def test_electron_detection_by_window_class_and_node(
        self, classifier: TechnologyClassifier
    ) -> None:
        signals = _signals(
            modules=["node.dll"],
            window_classes=["Chrome_WidgetWin_1"],
        )
        result = classifier.classify(signals)
        assert result.technology == ApplicationTechnology.ELECTRON
        assert result.recommended_adapter == AdapterType.ELECTRON_PLAYWRIGHT

    def test_electron_detection_by_exe_name(self, classifier: TechnologyClassifier) -> None:
        signals = _signals(
            exe_name="electron.exe",
            window_classes=["Chrome_WidgetWin_1"],
        )
        result = classifier.classify(signals)
        assert result.technology == ApplicationTechnology.ELECTRON

    def test_java_swing_detection(self, classifier: TechnologyClassifier) -> None:
        signals = _signals(
            exe_name="javaw.exe",
            modules=["jvm.dll", "awt.dll"],
            window_classes=["SunAwtFrame"],
        )
        result = classifier.classify(signals)
        assert result.technology == ApplicationTechnology.JAVA_SWING
        assert result.recommended_adapter == AdapterType.JAVA_ACCESS_BRIDGE

    def test_qt_detection_qt5(self, classifier: TechnologyClassifier) -> None:
        signals = _signals(
            modules=["Qt5Core.dll", "Qt5Widgets.dll"],
            window_classes=["Qt5QWindowIcon"],
        )
        result = classifier.classify(signals)
        assert result.technology == ApplicationTechnology.QT

    def test_citrix_detection_by_exe(self, classifier: TechnologyClassifier) -> None:
        signals = _signals(exe_name="wfica32.exe")
        result = classifier.classify(signals)
        assert result.technology == ApplicationTechnology.CITRIX
        assert result.recommended_adapter == AdapterType.SIKULI_IMAGE

    def test_rdp_detection(self, classifier: TechnologyClassifier) -> None:
        signals = _signals(exe_name="mstsc.exe")
        result = classifier.classify(signals)
        assert result.technology == ApplicationTechnology.RDP
        assert result.confidence >= 0.8

    def test_winui3_detection(self, classifier: TechnologyClassifier) -> None:
        signals = _signals(
            modules=["Microsoft.UI.Xaml.dll"],
            window_classes=["Microsoft.UI.Xaml.Controls.Frame"],
        )
        result = classifier.classify(signals)
        assert result.technology == ApplicationTechnology.WINUI3

    def test_unknown_signals_returns_result(self, classifier: TechnologyClassifier) -> None:
        signals = _signals()
        result = classifier.classify(signals)
        assert result is not None
        assert result.technology is not None

    def test_result_has_evidence(self, classifier: TechnologyClassifier) -> None:
        signals = _signals(
            modules=["PresentationCore.dll", "PresentationFramework.dll"],
            is_dotnet=True,
        )
        result = classifier.classify(signals)
        assert len(result.evidence) > 0

    def test_result_metadata_contains_all_scores(
        self, classifier: TechnologyClassifier
    ) -> None:
        signals = _signals(modules=["System.Windows.Forms.dll"])
        result = classifier.classify(signals)
        assert "all_scores" in result.metadata

    def test_confidence_capped_at_one(self, classifier: TechnologyClassifier) -> None:
        signals = _signals(
            modules=["PresentationCore.dll", "PresentationFramework.dll"],
            window_classes=["HwndWrapper"],
            is_dotnet=True,
        )
        result = classifier.classify(signals)
        assert result.confidence <= 1.0


# ---------------------------------------------------------------------------
# WindowsApplicationDetector tests
# ---------------------------------------------------------------------------


class TestWindowsApplicationDetector:
    @pytest.fixture
    def mock_inspector(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def wpf_signals(self) -> ProcessSignals:
        return _signals(
            modules=["presentationcore.dll", "presentationframework.dll"],
            window_classes=["HwndWrapper[MyApp;;]"],
            is_dotnet=True,
        )

    @pytest.fixture
    def detector(
        self, mock_inspector: MagicMock, wpf_signals: ProcessSignals
    ) -> WindowsApplicationDetector:
        mock_inspector.inspect_pid.return_value = wpf_signals
        mock_inspector.inspect_executable.return_value = wpf_signals
        return WindowsApplicationDetector(inspector=mock_inspector)

    def test_detect_by_pid_returns_result(
        self,
        detector: WindowsApplicationDetector,
        mock_inspector: MagicMock,
    ) -> None:
        result = detector.detect_by_pid(1234)
        assert result.technology == ApplicationTechnology.WPF
        mock_inspector.inspect_pid.assert_called_once_with(1234)

    def test_detect_by_pid_caches_result(
        self,
        detector: WindowsApplicationDetector,
        mock_inspector: MagicMock,
    ) -> None:
        detector.detect_by_pid(1234)
        detector.detect_by_pid(1234)
        assert mock_inspector.inspect_pid.call_count == 1

    def test_invalidate_cache_specific_pid(
        self,
        detector: WindowsApplicationDetector,
        mock_inspector: MagicMock,
    ) -> None:
        detector.detect_by_pid(1234)
        detector.invalidate_cache(1234)
        detector.detect_by_pid(1234)
        assert mock_inspector.inspect_pid.call_count == 2

    def test_invalidate_cache_all(
        self,
        detector: WindowsApplicationDetector,
        mock_inspector: MagicMock,
    ) -> None:
        detector.detect_by_pid(1234)
        detector.detect_by_pid(5678)
        detector.invalidate_cache()
        detector.detect_by_pid(1234)
        assert mock_inspector.inspect_pid.call_count == 3

    def test_detect_by_executable_delegates_to_inspector(
        self,
        detector: WindowsApplicationDetector,
        mock_inspector: MagicMock,
    ) -> None:
        result = detector.detect_by_executable("C:\\Apps\\claims.exe")
        assert result is not None
        mock_inspector.inspect_executable.assert_called_once_with("C:\\Apps\\claims.exe")

    def test_detect_by_pid_not_found_raises(
        self,
        mock_inspector: MagicMock,
    ) -> None:
        mock_inspector.inspect_pid.side_effect = ApplicationNotFoundException(
            identifier=9999
        )
        detector = WindowsApplicationDetector(inspector=mock_inspector)
        with pytest.raises(ApplicationNotFoundException):
            detector.detect_by_pid(9999)

    def test_detect_by_window_title_no_match_raises(
        self,
        detector: WindowsApplicationDetector,
    ) -> None:
        with patch(
            "desktop_automation_platform.adapters.detector.application_detector.process_utils.find_pids_by_window_title",
            return_value=[],
        ):
            with pytest.raises(ApplicationNotFoundException):
                detector.detect_by_window_title("NonexistentWindow")

    def test_detect_by_window_title_finds_first_pid(
        self,
        detector: WindowsApplicationDetector,
        mock_inspector: MagicMock,
    ) -> None:
        with patch(
            "desktop_automation_platform.adapters.detector.application_detector.process_utils.find_pids_by_window_title",
            return_value=[1111, 2222],
        ):
            detector.detect_by_window_title("Claims Desktop")
            mock_inspector.inspect_pid.assert_called_with(1111)

    def test_supported_technologies_excludes_unknown(
        self,
        detector: WindowsApplicationDetector,
    ) -> None:
        techs = detector.supported_technologies()
        assert ApplicationTechnology.UNKNOWN not in techs
        assert ApplicationTechnology.WPF in techs
