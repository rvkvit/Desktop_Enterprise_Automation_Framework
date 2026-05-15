"""
HealingListener — Robot Framework v3 listener that hooks into the test
lifecycle to drive the HealingTracker and write end-of-suite reports.

Usage in a Robot Framework test suite:

    *** Settings ***
    Library    DesktopAutomationLibrary    config_path=config.yaml  ...
    Library    desktop_automation_platform.recovery.robot_listener.HealingListener

Or register programmatically inside DesktopAutomationLibrary.__init__ so
teams don't need to add a separate Library import.

Report output
-------------
After every suite, a healing report is written to:
    <output_dir>/healing_report.yaml     (machine-readable)

A human-readable summary is logged at INFO level to the Robot Framework log.
"""

from __future__ import annotations

import os
from pathlib import Path

from desktop_automation_platform.recovery.healing_tracker import HealingTracker
from desktop_automation_platform.utils.logger import get_logger

_log = get_logger(__name__)

ROBOT_LISTENER_API_VERSION = 3


class HealingListener:
    """
    Robot Framework listener that wraps HealingTracker into the RF lifecycle.

    Registered automatically by DesktopAutomationLibrary when
    ``healing_report=True`` (the default).
    """

    ROBOT_LISTENER_API_VERSION = 3

    def __init__(self, output_dir: str = "") -> None:
        self._output_dir = output_dir or os.getcwd()
        self._tracker = HealingTracker.instance()

    # ------------------------------------------------------------------
    # RF listener hooks
    # ------------------------------------------------------------------

    def start_suite(self, data: object, result: object) -> None:
        self._tracker.reset()
        _log.debug("healing_tracker_reset")

    def start_test(self, data: object, result: object) -> None:
        try:
            test_name = getattr(result, "name", "<unknown>")
            self._tracker.set_current_test(test_name)
        except Exception:
            pass

    def end_suite(self, data: object, result: object) -> None:
        summary = self._tracker.summary()
        try:
            from robot.api import logger as robot_logger
            robot_logger.info(summary, html=False)
        except Exception:
            _log.info("healing_summary", summary=summary)

        if self._tracker.has_healed():
            self._write_yaml_report()

    # ------------------------------------------------------------------
    # Report writing
    # ------------------------------------------------------------------

    def _write_yaml_report(self) -> None:
        try:
            out = Path(self._output_dir) / "healing_report.yaml"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(self._tracker.yaml_report(), encoding="utf-8")
            _log.info("healing_report_written", path=str(out))
        except Exception as exc:
            _log.warning("healing_report_write_failed", error=str(exc))
