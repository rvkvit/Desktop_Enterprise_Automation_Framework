"""
WindowsApplicationDetector — concrete IApplicationDetector for Windows desktop.

Orchestrates the full detection pipeline:
  ProcessInspector → ProcessSignals → TechnologyClassifier → DetectionResult

Results are cached per PID for the lifetime of the detector instance to
avoid redundant process inspection on repeated queries within the same run.
"""

from __future__ import annotations

from desktop_automation_platform.adapters.detector.process_inspector import ProcessInspector
from desktop_automation_platform.adapters.detector.technology_classifier import (
    TechnologyClassifier,
)
from desktop_automation_platform.core.exceptions import ApplicationNotFoundException
from desktop_automation_platform.core.interfaces.application_detector import IApplicationDetector
from desktop_automation_platform.core.models import ApplicationTechnology, DetectionResult
from desktop_automation_platform.utils import process_utils
from desktop_automation_platform.utils.logger import get_logger

_log = get_logger(__name__)


class WindowsApplicationDetector(IApplicationDetector):
    """
    Windows-specific application technology detector.

    Thread-safety: the PID cache is not protected by a lock. In the
    typical single-threaded Robot Framework execution model this is fine.
    For parallel execution, wrap the cache operations with a threading.Lock.
    """

    def __init__(
        self,
        inspector: ProcessInspector | None = None,
        classifier: TechnologyClassifier | None = None,
    ) -> None:
        self._inspector = inspector or ProcessInspector()
        self._classifier = classifier or TechnologyClassifier()
        self._pid_cache: dict[int, DetectionResult] = {}

    # ------------------------------------------------------------------
    # IApplicationDetector
    # ------------------------------------------------------------------

    def detect_by_pid(self, process_id: int) -> DetectionResult:
        """
        Inspect the running process and classify its technology.

        Results are cached: repeated calls for the same PID return the
        first result (assumes the process does not change its technology
        at runtime, which is always true in practice).
        """
        if process_id in self._pid_cache:
            return self._pid_cache[process_id]

        _log.info("detecting_technology_by_pid", pid=process_id)
        signals = self._inspector.inspect_pid(process_id)
        result = self._classifier.classify(signals)

        _log.info(
            "technology_detected",
            pid=process_id,
            technology=result.technology.value,
            confidence=result.confidence,
            adapter=result.recommended_adapter.value,
            evidence=result.evidence,
        )

        self._pid_cache[process_id] = result
        return result

    def detect_by_executable(self, executable_path: str) -> DetectionResult:
        """
        Classify an executable without launching it.

        Only PE-level signals are available; confidence will typically be
        lower than detect_by_pid for the same application.
        """
        _log.info("detecting_technology_by_executable", executable=executable_path)
        signals = self._inspector.inspect_executable(executable_path)
        result = self._classifier.classify(signals)

        _log.info(
            "technology_detected_from_exe",
            executable=executable_path,
            technology=result.technology.value,
            confidence=result.confidence,
            adapter=result.recommended_adapter.value,
        )
        return result

    def detect_by_window_title(self, window_title: str) -> DetectionResult:
        """
        Find the first process with a matching window title, then detect.
        """
        _log.info("detecting_technology_by_window_title", title=window_title)
        pids = process_utils.find_pids_by_window_title(window_title, partial=True)
        if not pids:
            raise ApplicationNotFoundException(identifier=window_title)
        return self.detect_by_pid(pids[0])

    def supported_technologies(self) -> list[ApplicationTechnology]:
        return [t for t in ApplicationTechnology if t != ApplicationTechnology.UNKNOWN]

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def invalidate_cache(self, process_id: int | None = None) -> None:
        """
        Clear cached detection result for ``process_id``, or clear all
        if ``process_id`` is None.
        """
        if process_id is None:
            self._pid_cache.clear()
        else:
            self._pid_cache.pop(process_id, None)
