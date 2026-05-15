"""
IApplicationDetector — automatic desktop technology classification.

The detector inspects a running process (by PID or executable path) and
returns a ``DetectionResult`` that the ``AdapterManager`` uses to select
the optimal adapter without manual configuration.

Detection is a best-effort heuristic. The ``confidence`` score lets callers
decide whether to trust the recommendation or fall back to a configured
override.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from desktop_automation_platform.core.models import ApplicationTechnology, DetectionResult


class IApplicationDetector(ABC):
    """
    Detects the technology stack of a desktop application from runtime
    process signals (loaded modules, window class names, file metadata).
    """

    @abstractmethod
    def detect_by_pid(self, process_id: int) -> DetectionResult:
        """
        Analyse a running process by its PID and return the best technology
        match with a confidence score and supporting evidence.

        Raises ``ApplicationNotFoundException`` if the PID does not exist.
        """
        ...

    @abstractmethod
    def detect_by_executable(self, executable_path: str) -> DetectionResult:
        """
        Analyse an executable file (before launch) using PE metadata,
        manifest inspection, and embedded resources.

        Useful when the process is not yet running.
        Raises ``ApplicationNotFoundException`` if the file does not exist.
        """
        ...

    @abstractmethod
    def detect_by_window_title(self, window_title: str) -> DetectionResult:
        """
        Find the process whose main window matches ``window_title`` and
        delegate to ``detect_by_pid``.

        Supports partial title matching.
        Raises ``ApplicationNotFoundException`` if no matching window exists.
        """
        ...

    @abstractmethod
    def supported_technologies(self) -> list[ApplicationTechnology]:
        """Return all technologies this detector implementation can recognise."""
        ...
