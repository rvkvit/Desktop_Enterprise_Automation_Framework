"""
IApplicationAdapter — primary automation contract.

Every desktop adapter (FlaUI, WinAppDriver, pywinauto, etc.) must implement
this interface in full. Robot Framework keywords call only this interface,
never the adapter directly, ensuring the keyword layer is 100% adapter-agnostic.

Design notes
------------
* All operations return ``ActionResult`` instead of raising exceptions.
  Callers inspect ``ActionResult.status`` and call
  ``result.raise_if_failed()`` when a hard failure is required.
* ``ApplicationSession`` is the only state carrier across calls.
  Adapters must store all native handles inside ``session.native_session``.
* ``UnifiedLocator`` carries the full fallback chain; the adapter or the
  locator engine iterates it — do not strip fallbacks before passing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from desktop_automation_platform.core.models import (
    ActionResult,
    AdapterType,
    ApplicationInfo,
    ApplicationSession,
    ApplicationTechnology,
    UnifiedLocator,
)

if TYPE_CHECKING:
    from desktop_automation_platform.config.schema import ApplicationConfig, PlatformConfig


class IApplicationAdapter(ABC):
    """
    Unified automation contract for desktop application adapters.

    All 20 operations required by the Robot Framework keyword layer are
    declared here. Every concrete adapter must implement all methods;
    partial implementations raise ``NotImplementedError`` at runtime.
    """

    # ------------------------------------------------------------------
    # Adapter identity
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def adapter_type(self) -> AdapterType:
        """Unique identifier for this adapter implementation."""
        ...

    @property
    @abstractmethod
    def supported_technologies(self) -> list[ApplicationTechnology]:
        """
        Application technologies this adapter can automate.
        Used by the AdapterManager for automatic adapter selection.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """
        Return True if the adapter's native runtime dependencies are present
        and the platform environment supports this adapter.

        Called by AdapterManager before registering or using an adapter.
        Must never raise — return False on any error.
        """
        ...

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    def launch_application(
        self,
        app_info: ApplicationInfo,
        config: "PlatformConfig",
    ) -> ApplicationSession:
        """
        Launch the target desktop application and return an active session.

        The returned session must have ``state == SessionState.ACTIVE``.
        Raises ``ApplicationLaunchException`` if the process cannot start.
        """
        ...

    @abstractmethod
    def attach_application(
        self,
        process_id: int,
        app_info: ApplicationInfo | None = None,
    ) -> ApplicationSession:
        """
        Attach to an already-running application by process ID.

        Raises ``ApplicationNotFoundException`` if no matching process exists.
        """
        ...

    @abstractmethod
    def close_application(self, session: ApplicationSession) -> None:
        """
        Close the application and release all adapter-held resources.

        After this call, ``session.state`` must be ``SessionState.CLOSED``.
        Must not raise even if the process is already gone.
        """
        ...

    # ------------------------------------------------------------------
    # Mouse interactions
    # ------------------------------------------------------------------

    @abstractmethod
    def click(
        self,
        locator: UnifiedLocator,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> ActionResult:
        """Single left-click on the element resolved by ``locator``."""
        ...

    @abstractmethod
    def double_click(
        self,
        locator: UnifiedLocator,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> ActionResult:
        """Double left-click on the element resolved by ``locator``."""
        ...

    @abstractmethod
    def right_click(
        self,
        locator: UnifiedLocator,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> ActionResult:
        """Right-click (context menu) on the element resolved by ``locator``."""
        ...

    @abstractmethod
    def drag_and_drop(
        self,
        source_locator: UnifiedLocator,
        target_locator: UnifiedLocator,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> ActionResult:
        """Drag the source element and drop it onto the target element."""
        ...

    # ------------------------------------------------------------------
    # Keyboard interactions
    # ------------------------------------------------------------------

    @abstractmethod
    def input_text(
        self,
        locator: UnifiedLocator,
        text: str,
        session: ApplicationSession,
        clear_first: bool = True,
        **kwargs: Any,
    ) -> ActionResult:
        """Type ``text`` into the element resolved by ``locator``."""
        ...

    @abstractmethod
    def send_keys(
        self,
        locator: UnifiedLocator,
        keys: str,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> ActionResult:
        """
        Send raw key sequences (e.g. ``{ENTER}``, ``^a``) to the element.
        Key syntax must follow the platform-neutral key notation defined in
        ``locator_engine.key_notation``.
        """
        ...

    @abstractmethod
    def clear_text(
        self,
        locator: UnifiedLocator,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> ActionResult:
        """Clear all text content from the element resolved by ``locator``."""
        ...

    # ------------------------------------------------------------------
    # Element state queries
    # ------------------------------------------------------------------

    @abstractmethod
    def get_text(
        self,
        locator: UnifiedLocator,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> str:
        """Return the text/value of the element resolved by ``locator``."""
        ...

    @abstractmethod
    def get_element_attribute(
        self,
        locator: UnifiedLocator,
        attribute: str,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> str | None:
        """
        Return a named attribute of the element resolved by ``locator``.
        Returns ``None`` if the attribute does not exist.
        """
        ...

    @abstractmethod
    def element_exists(
        self,
        locator: UnifiedLocator,
        session: ApplicationSession,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> bool:
        """
        Return True if the element is present in the UI tree within ``timeout``.
        Must never raise — return False on any resolution failure.
        """
        ...

    @abstractmethod
    def wait_for_element(
        self,
        locator: UnifiedLocator,
        session: ApplicationSession,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> ActionResult:
        """
        Block until the element appears or ``timeout`` elapses.

        Returns ``ActionResult`` with ``status=TIMEOUT`` if not found in time.
        """
        ...

    # ------------------------------------------------------------------
    # List / combo selection
    # ------------------------------------------------------------------

    @abstractmethod
    def select_item(
        self,
        locator: UnifiedLocator,
        item: str,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> ActionResult:
        """Select ``item`` from a list, combo box, or drop-down control."""
        ...

    # ------------------------------------------------------------------
    # Window management
    # ------------------------------------------------------------------

    @abstractmethod
    def maximize_window(
        self,
        session: ApplicationSession,
        window_title: str | None = None,
    ) -> ActionResult:
        """Maximize the application main window or a named window."""
        ...

    @abstractmethod
    def minimize_window(
        self,
        session: ApplicationSession,
        window_title: str | None = None,
    ) -> ActionResult:
        """Minimize the application main window or a named window."""
        ...

    @abstractmethod
    def switch_window(
        self,
        window_title: str,
        session: ApplicationSession,
        timeout: float | None = None,
    ) -> ActionResult:
        """
        Set focus to the window whose title matches ``window_title``.
        Supports partial title matching.
        """
        ...

    # ------------------------------------------------------------------
    # Screenshot
    # ------------------------------------------------------------------

    @abstractmethod
    def take_screenshot(
        self,
        session: ApplicationSession,
        filename: str | None = None,
    ) -> str:
        """
        Capture a screenshot of the application window.
        Returns the absolute path to the saved image file.
        """
        ...
