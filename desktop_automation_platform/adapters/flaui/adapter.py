"""
FlaUIAdapter — primary desktop automation adapter.

Implements all 20 operations of IApplicationAdapter using FlaUI .NET interop
via pythonnet.  This is the production adapter for:
  WPF · WinForms · WinUI 3 · MAUI · Win32 · Windows Packaged Apps

Session state
-------------
``session.native_session`` is a dict with these keys:
    "application"  → FlaUI Application object
    "automation"   → UIA3Automation (or UIA2Automation)
    "main_window"  → AutomationElement for the current main window

The dict is used instead of a dedicated dataclass so the FlaUI types (which
live inside the CLR) do not leak into the platform's type signatures.

Thread safety
-------------
FlaUI itself is not thread-safe for concurrent window operations. The adapter
follows the same constraint: use one adapter instance per session, one session
per thread.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from desktop_automation_platform.adapters.base_adapter import BaseDesktopAdapter
from desktop_automation_platform.adapters.flaui.automation_factory import (
    create_automation,
    is_flaui_available,
)
from desktop_automation_platform.adapters.flaui.element_resolver import FlaUIElementResolver
from desktop_automation_platform.adapters.flaui.translator import FlaUILocatorTranslator
from desktop_automation_platform.core.exceptions import (
    ApplicationLaunchException,
    ApplicationNotFoundException,
    ElementNotFoundException,
    SessionNotActiveException,
)
from desktop_automation_platform.core.models import (
    ActionResult,
    ActionStatus,
    AdapterType,
    ApplicationInfo,
    ApplicationSession,
    ApplicationTechnology,
    SessionState,
    UnifiedLocator,
)
from desktop_automation_platform.utils.logger import get_logger

if TYPE_CHECKING:
    from desktop_automation_platform.config.schema import PlatformConfig
    from desktop_automation_platform.core.interfaces.screenshot_manager import IScreenshotManager

_log = get_logger(__name__)


class FlaUIAdapter(BaseDesktopAdapter):
    """
    Full IApplicationAdapter implementation backed by FlaUI + UIA3.
    """

    def __init__(
        self,
        config: "PlatformConfig",
        screenshot_manager: "IScreenshotManager",
    ) -> None:
        super().__init__(config=config, screenshot_manager=screenshot_manager)
        self._automation: Any = None
        self._resolver: FlaUIElementResolver | None = None
        self._translator: FlaUILocatorTranslator | None = None
        self._automation_type = config.adapters.flaui.automation_type

        from desktop_automation_platform.recovery import build_default_flaui_recovery_manager
        self._recovery_manager = build_default_flaui_recovery_manager()

    # ------------------------------------------------------------------
    # Lazy initialisation of FlaUI runtime
    # ------------------------------------------------------------------

    def _ensure_automation(self) -> Any:
        """Return the FlaUI automation instance, creating it on first call."""
        if self._automation is None:
            self._automation = create_automation(self._automation_type)
            self._resolver = FlaUIElementResolver(self._automation)
            self._translator = FlaUILocatorTranslator(self._automation)
            _log.debug("flaui_automation_initialised", type=self._automation_type)
        return self._automation

    def _get_resolver(self) -> FlaUIElementResolver:
        self._ensure_automation()
        assert self._resolver is not None
        return self._resolver

    def _get_recovery_native_context(self, session: ApplicationSession) -> dict:
        native = session.native_session if isinstance(session.native_session, dict) else {}
        return {
            "automation": native.get("automation"),
            "main_window": native.get("main_window"),
            "application": native.get("application"),
            "native_session_dict": native,   # mutable — StaleWindowStrategy updates main_window
        }

    # ------------------------------------------------------------------
    # IApplicationAdapter — identity
    # ------------------------------------------------------------------

    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.FLAUI

    @property
    def supported_technologies(self) -> list[ApplicationTechnology]:
        return [
            ApplicationTechnology.WPF,
            ApplicationTechnology.WINFORMS,
            ApplicationTechnology.WINUI3,
            ApplicationTechnology.MAUI,
            ApplicationTechnology.WIN32,
            ApplicationTechnology.PACKAGED,
        ]

    def is_available(self) -> bool:
        return is_flaui_available()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def launch_application(
        self,
        app_info: ApplicationInfo,
        config: "PlatformConfig",
    ) -> ApplicationSession:
        """
        Launch the executable and wait for the main window to appear.

        Uses FlaUI's ``Application.Launch`` which starts the process and
        attaches to it for full UIA introspection.
        """
        if not app_info.executable:
            raise ApplicationLaunchException(
                app_name=app_info.name,
                executable="<none>",
                reason="ApplicationInfo.executable is required for launch_application",
            )

        automation = self._ensure_automation()
        _log.info(
            "launching_application",
            name=app_info.name,
            executable=app_info.executable,
            adapter="flaui",
        )

        try:
            from FlaUI.Core import Application  # type: ignore[import]

            # FlaUI 4.x: Application.Launch is a static method, not an instance method.
            args = " ".join(app_info.launch_arguments) if app_info.launch_arguments else None
            if args:
                flaui_app = Application.Launch(app_info.executable, args)
            else:
                flaui_app = Application.Launch(app_info.executable)
        except Exception as exc:
            raise ApplicationLaunchException(
                app_name=app_info.name,
                executable=app_info.executable,
                reason=str(exc),
                original_error=exc,
            ) from exc

        # Wait for main window to appear
        launch_timeout = config.application.launch_timeout_seconds
        main_window = self._wait_for_main_window(flaui_app, automation, launch_timeout, app_info)

        session = ApplicationSession(
            app_info=app_info,
            adapter_type=AdapterType.FLAUI,
            native_session={
                "application": flaui_app,
                "automation": automation,
                "main_window": main_window,
            },
        )
        session.mark_active()
        _log.info(
            "application_launched",
            name=app_info.name,
            session_id=session.session_id,
            window_title=self._safe_window_title(main_window),
        )
        return session

    def attach_application(
        self,
        process_id: int,
        app_info: ApplicationInfo | None = None,
    ) -> ApplicationSession:
        """Attach to a running process by PID."""
        import psutil

        if not psutil.pid_exists(process_id):
            raise ApplicationNotFoundException(identifier=process_id)

        automation = self._ensure_automation()

        try:
            from FlaUI.Core import Application  # type: ignore[import]

            flaui_app = Application.Attach(process_id)
        except Exception as exc:
            raise ApplicationNotFoundException(identifier=process_id) from exc

        timeout = self._config.execution.timeout
        main_window = self._wait_for_main_window(flaui_app, automation, timeout)

        resolved_info = app_info or ApplicationInfo(
            name=f"Process-{process_id}",
            process_id=process_id,
        )

        session = ApplicationSession(
            app_info=resolved_info,
            adapter_type=AdapterType.FLAUI,
            native_session={
                "application": flaui_app,
                "automation": automation,
                "main_window": main_window,
            },
        )
        session.mark_active()
        _log.info(
            "application_attached",
            pid=process_id,
            session_id=session.session_id,
        )
        return session

    def close_application(self, session: ApplicationSession) -> None:
        """Close the application gracefully, then force-kill if needed."""
        native = self._get_native_or_none(session)
        if native is not None:
            app = native.get("application")
            if app is not None:
                try:
                    app.Close()
                    _log.info("application_closed_gracefully", session_id=session.session_id)
                except Exception:
                    pass
                try:
                    app.Kill()
                except Exception:
                    pass
            # Dispose the automation instance resources
            automation = native.get("automation")
            if automation is not None:
                try:
                    automation.Dispose()
                except Exception:
                    pass
        session.mark_closed()

    # ------------------------------------------------------------------
    # Element resolution helper
    # ------------------------------------------------------------------

    def _resolve_element(
        self,
        locator: UnifiedLocator,
        session: ApplicationSession,
    ) -> tuple[Any, "LocatorDefinition"]:  # type: ignore[name-defined]
        """
        Try each strategy in the locator chain and return (element, used_locator).
        Raises ``ElementNotFoundException`` if all strategies fail.
        """
        native = self._get_native(session)
        main_window = native["main_window"]
        resolver = self._get_resolver()
        timeout = self._config.execution.timeout
        strategies_tried: list[str] = []

        # Resolve scope element if set
        scope_element: Any = None
        if locator.scope:
            scope_loc = UnifiedLocator(
                name=locator.scope,
                primary=UnifiedLocator(  # type: ignore[arg-type]
                    name=locator.scope,
                    primary=None,  # type: ignore[arg-type]
                ).primary,
            )
            # Simplified: if scope is set, just use main_window for now
            # Full scope resolution handled by locator_engine in Phase 5
            scope_element = main_window

        for loc_def in locator.all_strategies():
            strategies_tried.append(loc_def.strategy.value)
            effective_timeout = loc_def.timeout or timeout
            try:
                # Skip strategies the FlaUI translator can't handle
                if self._translator and not self._translator.supports_strategy(
                    loc_def.strategy.value
                ):
                    _log.debug(
                        "strategy_skipped",
                        strategy=loc_def.strategy.value,
                        locator=locator.name,
                        adapter="flaui",
                    )
                    continue

                element = resolver.find_element(
                    root=scope_element or main_window,
                    locator=loc_def,
                    timeout_seconds=effective_timeout,
                    poll_interval_seconds=self._config.execution.poll_interval,
                )
                return element, loc_def
            except ElementNotFoundException:
                continue

        raise ElementNotFoundException(
            locator_name=locator.name,
            strategies_tried=strategies_tried,
            timeout_seconds=timeout,
        )

    # ------------------------------------------------------------------
    # Mouse operations
    # ------------------------------------------------------------------

    def click(
        self,
        locator: UnifiedLocator,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> ActionResult:
        def _action() -> None:
            element, _ = self._resolve_element(locator, session)
            element.Click()

        return self._execute_with_fallback(
            action_name="click",
            native_fn_factory=self._make_click_factory(session),
            locator=locator,
            session=session,
        )

    def double_click(
        self,
        locator: UnifiedLocator,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> ActionResult:
        return self._execute_with_fallback(
            action_name="double_click",
            native_fn_factory=self._make_double_click_factory(session),
            locator=locator,
            session=session,
        )

    def right_click(
        self,
        locator: UnifiedLocator,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> ActionResult:
        return self._execute_with_fallback(
            action_name="right_click",
            native_fn_factory=self._make_right_click_factory(session),
            locator=locator,
            session=session,
        )

    def drag_and_drop(
        self,
        source_locator: UnifiedLocator,
        target_locator: UnifiedLocator,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> ActionResult:
        def _action() -> None:
            src_element, _ = self._resolve_element(source_locator, session)
            tgt_element, _ = self._resolve_element(target_locator, session)
            src_rect = src_element.BoundingRectangle
            tgt_rect = tgt_element.BoundingRectangle

            from FlaUI.Core.Input import Mouse  # type: ignore[import]
            import System  # type: ignore[import]

            src_center = System.Drawing.Point(
                int(src_rect.X + src_rect.Width / 2),
                int(src_rect.Y + src_rect.Height / 2),
            )
            tgt_center = System.Drawing.Point(
                int(tgt_rect.X + tgt_rect.Width / 2),
                int(tgt_rect.Y + tgt_rect.Height / 2),
            )
            Mouse.MoveTo(src_center)
            time.sleep(0.1)
            Mouse.Down(System.Windows.Input.MouseButton.Left)
            time.sleep(0.2)
            Mouse.MoveTo(tgt_center)
            time.sleep(0.1)
            Mouse.Up(System.Windows.Input.MouseButton.Left)

        return self._execute_action(
            action_name="drag_and_drop",
            native_fn=_action,
            session=session,
            locator=source_locator,
            locator_used=source_locator.primary,
        )

    # ------------------------------------------------------------------
    # Keyboard operations
    # ------------------------------------------------------------------

    def input_text(
        self,
        locator: UnifiedLocator,
        text: str,
        session: ApplicationSession,
        clear_first: bool = True,
        **kwargs: Any,
    ) -> ActionResult:
        def _action() -> None:
            element, _ = self._resolve_element(locator, session)
            if clear_first:
                try:
                    element.Patterns.Value.Pattern.SetValue("")
                except Exception:
                    pass
            try:
                element.Patterns.Value.Pattern.SetValue(text)
            except Exception:
                # Fallback: focus + keyboard type
                element.Focus()
                if clear_first:
                    from FlaUI.Core.Input import Keyboard  # type: ignore[import]
                    from FlaUI.Core.WindowsAPI import VirtualKeyShort  # type: ignore[import]

                    Keyboard.TypeSimultaneously([VirtualKeyShort.CONTROL, VirtualKeyShort.KEY_A])
                    Keyboard.Type(text)
                else:
                    from FlaUI.Core.Input import Keyboard  # type: ignore[import]

                    Keyboard.Type(text)

        return self._execute_action(
            action_name="input_text",
            native_fn=_action,
            session=session,
            locator=locator,
            locator_used=locator.primary,
        )

    def send_keys(
        self,
        locator: UnifiedLocator,
        keys: str,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> ActionResult:
        def _action() -> None:
            element, _ = self._resolve_element(locator, session)
            element.Focus()
            from FlaUI.Core.Input import Keyboard  # type: ignore[import]

            Keyboard.Type(self._translate_keys(keys))

        return self._execute_action(
            action_name="send_keys",
            native_fn=_action,
            session=session,
            locator=locator,
            locator_used=locator.primary,
        )

    def clear_text(
        self,
        locator: UnifiedLocator,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> ActionResult:
        def _action() -> None:
            element, _ = self._resolve_element(locator, session)
            try:
                element.Patterns.Value.Pattern.SetValue("")
            except Exception:
                element.Focus()
                from FlaUI.Core.Input import Keyboard  # type: ignore[import]
                from FlaUI.Core.WindowsAPI import VirtualKeyShort  # type: ignore[import]

                Keyboard.TypeSimultaneously([VirtualKeyShort.CONTROL, VirtualKeyShort.KEY_A])
                Keyboard.Type("")

        return self._execute_action(
            action_name="clear_text",
            native_fn=_action,
            session=session,
            locator=locator,
            locator_used=locator.primary,
        )

    # ------------------------------------------------------------------
    # Element state queries
    # ------------------------------------------------------------------

    def get_text(
        self,
        locator: UnifiedLocator,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> str:
        element, _ = self._resolve_element(locator, session)
        # Try Value pattern first (TextBox, Edit), then Name (Label, Text)
        try:
            val = element.Patterns.Value.Pattern.Value
            if val is not None:
                return str(val)
        except Exception:
            pass
        try:
            return str(element.Name or "")
        except Exception:
            return ""

    def get_element_attribute(
        self,
        locator: UnifiedLocator,
        attribute: str,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> str | None:
        element, _ = self._resolve_element(locator, session)
        attr_map: dict[str, str] = {
            "name": "Name",
            "automation_id": "AutomationId",
            "class_name": "ClassName",
            "control_type": "ControlType",
            "is_enabled": "IsEnabled",
            "is_offscreen": "IsOffscreen",
            "help_text": "HelpText",
            "accelerator_key": "AcceleratorKey",
        }
        uia_attr = attr_map.get(attribute.lower(), attribute)
        try:
            val = getattr(element, uia_attr, None)
            return str(val) if val is not None else None
        except Exception:
            return None

    def element_exists(
        self,
        locator: UnifiedLocator,
        session: ApplicationSession,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> bool:
        try:
            self._assert_session_active(session)
            native = self._get_native(session)
            main_window = native["main_window"]
            resolver = self._get_resolver()
            effective_timeout = timeout or 2.0  # short timeout for exists check

            for loc_def in locator.all_strategies():
                if self._translator and not self._translator.supports_strategy(
                    loc_def.strategy.value
                ):
                    continue
                if resolver.element_exists(main_window, loc_def, effective_timeout):
                    return True
            return False
        except Exception:
            return False

    def wait_for_element(
        self,
        locator: UnifiedLocator,
        session: ApplicationSession,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> ActionResult:
        import time as _time

        start = _time.monotonic()
        effective_timeout = timeout or self._config.execution.timeout

        def _action() -> None:
            self._resolve_element(locator, session)

        result = self._execute_action(
            action_name="wait_for_element",
            native_fn=_action,
            session=session,
            locator=locator,
            locator_used=locator.primary,
        )
        if not result.is_success():
            result.status = ActionStatus.TIMEOUT
        return result

    # ------------------------------------------------------------------
    # List / combo selection
    # ------------------------------------------------------------------

    def select_item(
        self,
        locator: UnifiedLocator,
        item: str,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> ActionResult:
        def _action() -> None:
            element, _ = self._resolve_element(locator, session)
            # Strategy 1: ExpandCollapse + SelectionItem
            try:
                element.Patterns.ExpandCollapse.Pattern.Expand()
                time.sleep(0.2)
            except Exception:
                pass

            # Find the item in the expanded list
            native = self._get_native(session)
            main_window = native["main_window"]
            resolver = self._get_resolver()

            from desktop_automation_platform.core.models import (
                LocatorDefinition,
                LocatorStrategy,
            )

            item_loc = LocatorDefinition(strategy=LocatorStrategy.NAME, value=item)
            try:
                item_element = resolver.find_element(
                    main_window, item_loc, timeout_seconds=5.0
                )
                item_element.Patterns.SelectionItem.Pattern.Select()
                return
            except Exception:
                pass

            # Strategy 2: Value pattern (some combo boxes accept text directly)
            try:
                element.Patterns.Value.Pattern.SetValue(item)
            except Exception as exc:
                raise RuntimeError(f"Could not select '{item}': {exc}") from exc

        return self._execute_action(
            action_name="select_item",
            native_fn=_action,
            session=session,
            locator=locator,
            locator_used=locator.primary,
        )

    # ------------------------------------------------------------------
    # Window management
    # ------------------------------------------------------------------

    def maximize_window(
        self,
        session: ApplicationSession,
        window_title: str | None = None,
    ) -> ActionResult:
        def _action() -> None:
            window = self._get_target_window(session, window_title)
            self._set_window_state(window, "Maximized")

        return self._execute_action(
            action_name="maximize_window",
            native_fn=_action,
            session=session,
        )

    def minimize_window(
        self,
        session: ApplicationSession,
        window_title: str | None = None,
    ) -> ActionResult:
        def _action() -> None:
            window = self._get_target_window(session, window_title)
            self._set_window_state(window, "Minimized")

        return self._execute_action(
            action_name="minimize_window",
            native_fn=_action,
            session=session,
        )

    def switch_window(
        self,
        window_title: str,
        session: ApplicationSession,
        timeout: float | None = None,
    ) -> ActionResult:
        def _action() -> None:
            resolver = self._get_resolver()
            automation = self._ensure_automation()
            effective_timeout = timeout or self._config.execution.timeout
            window = resolver.find_window_by_title(
                automation, window_title, partial=True, timeout_seconds=effective_timeout
            )
            native = self._get_native(session)
            native["main_window"] = window
            _log.info(
                "window_switched",
                title=window_title,
                session_id=session.session_id,
            )

        return self._execute_action(
            action_name="switch_window",
            native_fn=_action,
            session=session,
        )

    # ------------------------------------------------------------------
    # Screenshot
    # ------------------------------------------------------------------

    def take_screenshot(
        self,
        session: ApplicationSession,
        filename: str | None = None,
    ) -> str:
        return self._screenshot_manager.capture(session=session, label=filename)

    # ------------------------------------------------------------------
    # BaseDesktopAdapter abstract methods
    # ------------------------------------------------------------------

    def _native_maximize_window(
        self, session: ApplicationSession, window_title: str | None
    ) -> None:
        window = self._get_target_window(session, window_title)
        self._set_window_state(window, "Maximized")

    def _native_minimize_window(
        self, session: ApplicationSession, window_title: str | None
    ) -> None:
        window = self._get_target_window(session, window_title)
        self._set_window_state(window, "Minimized")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _make_click_factory(self, session: ApplicationSession):
        def factory(loc_def):
            def action():
                native = self._get_native(session)
                resolver = self._get_resolver()
                timeout = loc_def.timeout or self._config.execution.timeout
                element = resolver.find_element(native["main_window"], loc_def, timeout)
                element.Click()
            return action
        return factory

    def _make_double_click_factory(self, session: ApplicationSession):
        def factory(loc_def):
            def action():
                native = self._get_native(session)
                resolver = self._get_resolver()
                timeout = loc_def.timeout or self._config.execution.timeout
                element = resolver.find_element(native["main_window"], loc_def, timeout)
                element.DoubleClick()
            return action
        return factory

    def _make_right_click_factory(self, session: ApplicationSession):
        def factory(loc_def):
            def action():
                native = self._get_native(session)
                resolver = self._get_resolver()
                timeout = loc_def.timeout or self._config.execution.timeout
                element = resolver.find_element(native["main_window"], loc_def, timeout)
                element.RightClick()
            return action
        return factory

    @staticmethod
    def _wait_for_main_window(
        app: Any,
        automation: Any,
        timeout: float,
        app_info: "ApplicationInfo | None" = None,
    ) -> Any:
        """
        Poll until the application's main window is available.

        Handles the Windows 11 redirect case where the launched process (e.g.
        notepad.exe stub) exits immediately and the real app runs under a
        different process name (e.g. "Notepad").  When the original process
        exits we search for the process by the executable's stem and attach.
        """
        from pathlib import Path as _Path

        import System.Diagnostics  # type: ignore[import]
        from FlaUI.Core import Application  # type: ignore[import]

        deadline = time.monotonic() + timeout
        current_app = app
        exe_stem = (
            _Path(app_info.executable).stem if app_info and app_info.executable else ""
        )
        app_name = app_info.name if app_info else "<unknown>"
        executable = app_info.executable if app_info else "<unknown>"

        while time.monotonic() < deadline:
            try:
                window = current_app.GetMainWindow(automation)
                if window is not None:
                    return window
            except Exception as exc:
                err = str(exc).lower()
                # Windows 11: redirect stub process already exited — find real process.
                if exe_stem and ("not running" in err or "not find process" in err or "process" in err):
                    # Try several name casing variants (Windows 11 Notepad = "Notepad", etc.)
                    for candidate in {exe_stem, exe_stem.capitalize(), exe_stem.upper(), exe_stem.lower()}:
                        try:
                            procs = list(System.Diagnostics.Process.GetProcessesByName(candidate))
                            if procs:
                                current_app = Application.Attach(procs[0].Id)
                                _log.debug(
                                    "flaui_redirected_process_found",
                                    original_stem=exe_stem,
                                    found_name=candidate,
                                    pid=procs[0].Id,
                                )
                                break
                        except Exception:
                            pass
            time.sleep(0.3)

        raise ApplicationLaunchException(
            app_name=app_name,
            executable=executable,
            reason=f"Main window did not appear within {timeout}s",
        )

    @staticmethod
    def _safe_window_title(window: Any) -> str:
        try:
            return str(window.Name or "")
        except Exception:
            return "<unknown>"

    @staticmethod
    def _get_native(session: ApplicationSession) -> dict[str, Any]:
        if not isinstance(session.native_session, dict):
            raise RuntimeError(
                f"FlaUI adapter expects native_session to be a dict; "
                f"got {type(session.native_session)}"
            )
        return session.native_session  # type: ignore[return-value]

    @staticmethod
    def _get_native_or_none(session: ApplicationSession) -> dict[str, Any] | None:
        if isinstance(session.native_session, dict):
            return session.native_session  # type: ignore[return-value]
        return None

    def _get_target_window(self, session: ApplicationSession, window_title: str | None) -> Any:
        native = self._get_native(session)
        if window_title is None:
            return native["main_window"]
        # Find the named window
        resolver = self._get_resolver()
        automation = self._ensure_automation()
        return resolver.find_window_by_title(
            automation, window_title, partial=True, timeout_seconds=10.0
        )

    @staticmethod
    def _set_window_state(window: Any, state: str) -> None:
        try:
            from FlaUI.Core.Definitions import WindowVisualState  # type: ignore[import]

            target_state = getattr(WindowVisualState, state)
            window.Patterns.Window.Pattern.SetWindowVisualState(target_state)
        except Exception as exc:
            # Fallback: use Win32 ShowWindow
            _log.debug("window_state_fallback", state=state, error=str(exc))
            import ctypes

            try:
                hwnd = int(str(window.FrameworkAutomationElement.NativeWindowHandle))
                sw_map = {"Maximized": 3, "Minimized": 6, "Normal": 9}
                ctypes.windll.user32.ShowWindow(hwnd, sw_map.get(state, 9))
            except Exception:
                pass

    @staticmethod
    def _translate_keys(keys: str) -> str:
        """
        Translate platform-neutral key notation to FlaUI Keyboard.Type-compatible format.

        Platform-neutral notation uses {KEY} for special keys (mirroring Robot Framework).
        FlaUI's Keyboard.Type uses VirtualKeyShort internally; we translate here.

        Examples:
            {ENTER}  → actual Enter character (FlaUI handles it)
            {TAB}    → actual Tab character
            ^a       → Ctrl+A (handled via TypeSimultaneously separately if needed)
        """
        # Simple pass-through: FlaUI.Core.Input.Keyboard.Type handles most special chars
        # Full key-notation translation is in locator_engine.key_notation (Phase 5)
        return keys
