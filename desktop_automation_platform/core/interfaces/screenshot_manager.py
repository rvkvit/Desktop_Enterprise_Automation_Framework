"""
IScreenshotManager — screenshot capture, storage, and naming contract.

The screenshot manager abstracts where and how screenshots are stored.
All adapters delegate screenshot operations here rather than implementing
their own file I/O, ensuring consistent naming conventions, directory
structure, and retention policies across the platform.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from desktop_automation_platform.core.models import ApplicationSession


class IScreenshotManager(ABC):
    """Captures, names, and stores screenshots during test execution."""

    @abstractmethod
    def capture(
        self,
        session: ApplicationSession,
        label: str | None = None,
        subfolder: str | None = None,
    ) -> str:
        """
        Capture the current state of the application window.

        Parameters
        ----------
        session:
            Active session whose window is captured.
        label:
            Optional human-readable label embedded in the filename.
        subfolder:
            Sub-directory within the screenshots root for this capture.

        Returns the absolute path to the saved screenshot file.
        Raises ``AdapterOperationException`` on capture failure.
        """
        ...

    @abstractmethod
    def capture_on_failure(
        self,
        session: ApplicationSession,
        action_name: str,
        test_name: str | None = None,
    ) -> str | None:
        """
        Convenience wrapper for on-failure screenshots.

        Returns the path on success, or ``None`` if capture fails (never raises
        so that the original failure is not masked).
        """
        ...

    @abstractmethod
    def capture_element(
        self,
        session: ApplicationSession,
        bounding_rect: dict[str, int],
        label: str | None = None,
    ) -> str:
        """
        Capture a single element region by its bounding rectangle.

        ``bounding_rect`` must contain ``{x, y, width, height}`` in screen
        coordinates.
        """
        ...

    @abstractmethod
    def get_screenshot_directory(self) -> str:
        """Return the root screenshots output directory (absolute path)."""
        ...

    @abstractmethod
    def set_screenshot_directory(self, directory: str) -> None:
        """Change the root screenshots output directory at runtime."""
        ...

    @abstractmethod
    def purge_old_screenshots(self, max_age_days: int) -> int:
        """
        Delete screenshots older than ``max_age_days``.
        Returns the count of deleted files.
        """
        ...
