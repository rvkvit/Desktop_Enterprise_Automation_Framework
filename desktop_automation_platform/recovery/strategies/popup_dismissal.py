"""
PopupDismissalStrategy — closes unexpected modal dialogs that block element access.

Common cases:
  - "Do you want to save?" confirmation dialog
  - Expired session / timeout dialog
  - Windows UAC prompt
  - Application error/crash report dialog

Dismissal is attempted by pressing Escape, then Enter, then closing via the
Window pattern — stopping at the first that clears the blocker.
"""

from __future__ import annotations

from typing import Any

from desktop_automation_platform.core.models import ApplicationSession, UnifiedLocator
from desktop_automation_platform.utils.logger import get_logger

_log = get_logger(__name__)

# Dialog titles that indicate a blocking popup (case-insensitive substring match)
_KNOWN_POPUP_TITLES = [
    "confirm", "warning", "error", "alert", "save", "unsaved",
    "session expired", "timeout", "do you want", "are you sure",
    "microsoft visual c++", "stopped working", "not responding",
]


class PopupDismissalStrategy:
    """
    Tries to dismiss unexpected popup dialogs that are blocking element access.

    Works with FlaUI native context. No-op for other adapters (returns False).
    """

    heal_type = "popup_dismissed"

    def apply(
        self,
        locator: UnifiedLocator,
        session: ApplicationSession,
        native_context: dict[str, Any],
    ) -> bool:
        """
        Returns True if a popup was found and dismissed (even if dismiss failed
        — the caller's retry_fn determines actual success).
        """
        automation = native_context.get("automation")
        main_window = native_context.get("main_window")
        if automation is None or main_window is None:
            return False

        try:
            return self._dismiss_flaui(automation, main_window)
        except Exception as exc:
            _log.debug("popup_dismissal_error", error=str(exc))
            return False

    @staticmethod
    def _dismiss_flaui(automation: Any, main_window: Any) -> bool:
        try:
            from FlaUI.Core.Definitions import ControlType, TreeScope  # type: ignore[import]
            from FlaUI.Core.Input import Keyboard  # type: ignore[import]
            from FlaUI.Core.WindowsAPI import VirtualKeyShort  # type: ignore[import]
        except ImportError:
            return False

        # Look for child windows / dialogs of the main window
        try:
            from FlaUI.Core.Conditions import TrueCondition  # type: ignore[import]
            children = main_window.FindAll(TreeScope.Children, TrueCondition.Default)
        except Exception:
            return False

        dismissed = False
        for child in children:
            try:
                title = str(child.Name or "").lower()
                ct = str(child.ControlType).split(".")[-1]
                if ct not in ("Window", "Dialog", "Pane"):
                    continue
                if not any(kw in title for kw in _KNOWN_POPUP_TITLES):
                    # Not a known blocking popup — try anyway if it's a Window/Dialog
                    if ct not in ("Window", "Dialog"):
                        continue

                _log.info("popup_detected", title=title, control_type=ct)

                # Strategy 1: Escape key
                try:
                    Keyboard.TypeSimultaneously(VirtualKeyShort.ESC)
                    dismissed = True
                    _log.info("popup_dismissed_escape", title=title)
                    continue
                except Exception:
                    pass

                # Strategy 2: Close via Window pattern
                try:
                    wp = child.Patterns.Window
                    if wp and wp.IsSupported:
                        wp.Pattern.Close()
                        dismissed = True
                        _log.info("popup_dismissed_window_pattern", title=title)
                        continue
                except Exception:
                    pass

                # Strategy 3: Enter key (accepts defaults)
                try:
                    child.Focus()
                    Keyboard.TypeSimultaneously(VirtualKeyShort.RETURN)
                    dismissed = True
                    _log.info("popup_dismissed_enter", title=title)
                except Exception:
                    pass

            except Exception:
                continue

        return dismissed
