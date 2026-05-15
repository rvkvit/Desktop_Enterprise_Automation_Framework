"""
IReporter — enterprise test execution reporting contract.

The reporter receives structured events during test execution and produces
artefacts: JSON/HTML execution traces, adapter diagnostics, locator resolution
paths, and failure summaries integrated with Robot Framework's output.xml.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from desktop_automation_platform.core.models import ActionResult, ApplicationSession


class IReporter(ABC):
    """Receives execution events and produces structured reports."""

    @abstractmethod
    def begin_suite(self, suite_name: str, metadata: dict[str, Any] | None = None) -> None:
        """Signal the start of a Robot Framework test suite."""
        ...

    @abstractmethod
    def end_suite(self, suite_name: str, metadata: dict[str, Any] | None = None) -> None:
        """Signal the end of a Robot Framework test suite."""
        ...

    @abstractmethod
    def begin_test(self, test_name: str, metadata: dict[str, Any] | None = None) -> None:
        """Signal the start of a test case."""
        ...

    @abstractmethod
    def end_test(
        self,
        test_name: str,
        passed: bool,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Signal the end of a test case with pass/fail status."""
        ...

    @abstractmethod
    def record_action(
        self,
        result: ActionResult,
        session: ApplicationSession | None = None,
    ) -> None:
        """Record the outcome of a single keyword execution."""
        ...

    @abstractmethod
    def record_session_started(self, session: ApplicationSession) -> None:
        """Record that an automation session was successfully opened."""
        ...

    @abstractmethod
    def record_session_closed(self, session: ApplicationSession) -> None:
        """Record that an automation session was closed."""
        ...

    @abstractmethod
    def record_recovery_attempt(
        self,
        session: ApplicationSession,
        strategy_name: str,
        succeeded: bool,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a recovery strategy attempt and its outcome."""
        ...

    @abstractmethod
    def generate_report(self, output_directory: str) -> str:
        """
        Persist all accumulated execution data and produce the final report
        artefact. Returns the path to the primary output file.
        """
        ...

    @abstractmethod
    def attach_screenshot(
        self,
        screenshot_path: str,
        label: str | None = None,
    ) -> None:
        """Attach a screenshot to the current test's report entry."""
        ...
