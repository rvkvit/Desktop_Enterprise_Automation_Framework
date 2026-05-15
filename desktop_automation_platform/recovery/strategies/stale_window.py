"""
StaleWindowStrategy — re-attaches to the application when the main window
handle (HWND) has gone stale.

Stale window causes:
  - Application navigated to a new top-level window (wizard, new document)
  - Application performed an in-place window re-creation (splash → main)
  - Windows 11 packaged apps that re-host their window on first interaction

Recovery: scan all top-level windows for the application process, find the
new foreground window, and update session.native_session["main_window"].
"""

from __future__ import annotations

import time
from typing import Any

from desktop_automation_platform.core.models import ApplicationSession, UnifiedLocator
from desktop_automation_platform.utils.logger import get_logger

_log = get_logger(__name__)


class StaleWindowStrategy:
    """
    Re-attaches to the application's current main window when the cached
    window handle is stale.

    Works with FlaUI native context. No-op for other adapters.
    """

    heal_type = "stale_window"

    def apply(
        self,
        locator: UnifiedLocator,
        session: ApplicationSession,
        native_context: dict[str, Any],
    ) -> bool:
        flaui_app = native_context.get("application")
        automation = native_context.get("automation")
        native_dict = native_context.get("native_session_dict")  # mutable ref to session dict

        if flaui_app is None or automation is None or native_dict is None:
            return False

        try:
            return self._reattach_flaui(flaui_app, automation, native_dict)
        except Exception as exc:
            _log.debug("stale_window_recovery_error", error=str(exc))
            return False

    @staticmethod
    def _reattach_flaui(flaui_app: Any, automation: Any, native_dict: dict) -> bool:
        try:
            # Try GetMainWindow first — refreshes the window handle
            new_window = flaui_app.GetMainWindow(automation)
            if new_window is not None:
                old_runtime = str(native_dict.get("main_window", {}) or "")
                new_runtime = str(new_window.RuntimeId or "")
                if old_runtime != new_runtime:
                    native_dict["main_window"] = new_window
                    _log.info("stale_window_reattached", new_runtime_id=new_runtime)
                    return True
        except Exception:
            pass

        # Fallback: scan all windows for this process
        try:
            from FlaUI.Core import Application  # type: ignore[import]

            all_windows = flaui_app.GetAllTopLevelWindows(automation)
            if all_windows and len(all_windows) > 0:
                # Pick the first visible, non-minimised window
                for w in all_windows:
                    try:
                        is_offscreen = bool(w.IsOffscreen)
                        if not is_offscreen:
                            native_dict["main_window"] = w
                            _log.info("stale_window_reattached_scan", window_name=str(w.Name or ""))
                            return True
                    except Exception:
                        continue
        except Exception as exc:
            _log.debug("stale_window_scan_error", error=str(exc))

        return False
