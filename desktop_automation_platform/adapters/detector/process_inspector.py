"""
ProcessInspector — collects raw process signals for the TechnologyClassifier.

Gathers:
  - Loaded DLL/SO module names
  - Win32 window class names for all top-level windows
  - Process command-line
  - Executable name
  - .NET PE presence indicator

All collection is best-effort; individual failures are swallowed and logged
so that a permissions error on one signal doesn't abort the full inspection.
"""

from __future__ import annotations

from desktop_automation_platform.adapters.detector.technology_classifier import ProcessSignals
from desktop_automation_platform.core.exceptions import ApplicationNotFoundException
from desktop_automation_platform.utils import process_utils
from desktop_automation_platform.utils.logger import get_logger

_log = get_logger(__name__)


class ProcessInspector:
    """
    Builds a ``ProcessSignals`` snapshot for a given process.

    Designed to be injected into ``WindowsApplicationDetector`` but also
    usable standalone for diagnostics.
    """

    def inspect_pid(self, pid: int) -> ProcessSignals:
        """
        Collect all available signals for the process identified by ``pid``.

        Raises ``ApplicationNotFoundException`` if the PID does not exist.
        """
        info = process_utils.get_process_info(pid)
        if info is None:
            raise ApplicationNotFoundException(identifier=pid)

        exe_name = info.get("name", "") or ""
        modules = self._safe_get_modules(pid)
        window_classes = self._safe_get_window_classes(pid)
        cmdline = info.get("cmdline") or []
        exe_path = info.get("exe", "") or ""
        is_dotnet = self._check_dotnet(exe_path, modules)

        _log.debug(
            "process_inspected",
            pid=pid,
            exe=exe_name,
            module_count=len(modules),
            window_class_count=len(window_classes),
            is_dotnet=is_dotnet,
        )

        return ProcessSignals(
            pid=pid,
            exe_name=exe_name,
            modules=modules,
            window_class_names=window_classes,
            cmdline=cmdline,
            is_dotnet=is_dotnet,
        )

    def inspect_executable(self, executable_path: str) -> ProcessSignals:
        """
        Build a partial ``ProcessSignals`` from an executable file before launch.

        Only PE-derivable signals are available (no runtime modules, no window classes).
        """
        from pathlib import Path

        path = Path(executable_path)
        if not path.exists():
            raise ApplicationNotFoundException(identifier=executable_path)

        exe_name = path.name
        is_dotnet = process_utils.is_dotnet_executable(executable_path)

        _log.debug(
            "executable_inspected",
            executable=executable_path,
            is_dotnet=is_dotnet,
        )

        return ProcessSignals(
            pid=-1,
            exe_name=exe_name,
            modules=[],
            window_class_names=[],
            cmdline=[executable_path],
            is_dotnet=is_dotnet,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_get_modules(pid: int) -> list[str]:
        try:
            return process_utils.get_process_modules(pid)
        except Exception as exc:
            _log.debug("module_inspection_failed", pid=pid, error=str(exc))
            return []

    @staticmethod
    def _safe_get_window_classes(pid: int) -> list[str]:
        try:
            return process_utils.get_window_class_names(pid)
        except Exception as exc:
            _log.debug("window_class_inspection_failed", pid=pid, error=str(exc))
            return []

    @staticmethod
    def _check_dotnet(exe_path: str, modules: list[str]) -> bool:
        # Module list is the most reliable signal (available for running processes)
        if any(m in modules for m in ("mscoree.dll", "coreclr.dll", "clr.dll")):
            return True
        # Fall back to PE inspection for pre-launch detection
        if exe_path:
            return process_utils.is_dotnet_executable(exe_path)
        return False
