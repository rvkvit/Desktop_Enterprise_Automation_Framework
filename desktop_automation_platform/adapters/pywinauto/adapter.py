"""
PywinautoAdapter — IApplicationAdapter implementation using pywinauto.

Target technologies
-------------------
  Win32 · MFC · Qt (Win32 backend) · legacy VB6/Delphi apps

pywinauto supports two backends:
  ``uia``   — modern UIA (default) — works for Win32 apps with accessibility
  ``win32`` — low-level Win32 messages — works for apps without UIA support

Backend is selected via ``config.adapters.pywinauto.backend`` (default: "uia").

Session state
-------------
``session.native_session`` is a dict with keys:
    "app"          → pywinauto.Application instance
    "main_window"  → pywinauto WindowSpecification for the main window
    "backend"      → "uia" | "win32"

Install requirement: ``pip install pywinauto``
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from desktop_automation_platform.adapters.base_adapter import BaseDesktopAdapter
from desktop_automation_platform.adapters.pywinauto.element_resolver import (
    PywinautoElementResolver,
)
from desktop_automation_platform.core.exceptions import (
    ApplicationLaunchException,
    ApplicationNotFoundException,
    ElementNotFoundException,
)
from desktop_automation_platform.core.models import (
    ActionResult,
    ActionStatus,
    AdapterType,
    ApplicationInfo,
    ApplicationSession,
    ApplicationTechnology,
    LocatorDefinition,
    SessionState,
    UnifiedLocator,
)
from desktop_automation_platform.utils.logger import get_logger

if TYPE_CHECKING:
    from desktop_automation_platform.config.schema import PlatformConfig
    from desktop_automation_platform.core.interfaces.screenshot_manager import IScreenshotManager

_log = get_logger(__name__)


def _is_pywinauto_available() -> bool:
    try:
        import pywinauto  # noqa: F401
        return True
    except ImportError:
        return False


class PywinautoAdapter(BaseDesktopAdapter):
    """Full IApplicationAdapter backed by pywinauto."""

    def __init__(
        self,
        config: "PlatformConfig",
        screenshot_manager: "IScreenshotManager",
    ) -> None:
        super().__init__(config=config, screenshot_manager=screenshot_manager)
        self._backend: str = getattr(
            getattr(getattr(config, "adapters", None), "pywinauto", None),
            "backend",
            "uia",
        )
        self._resolver = PywinautoElementResolver(backend=self._backend)

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.PYWINAUTO

    @property
    def supported_technologies(self) -> list[ApplicationTechnology]:
        return [
            ApplicationTechnology.WIN32,
            ApplicationTechnology.WINFORMS,
            ApplicationTechnology.QT,
            ApplicationTechnology.MFC,
        ]

    def is_available(self) -> bool:
        return _is_pywinauto_available()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def launch_application(
        self,
        app_info: ApplicationInfo,
        config: "PlatformConfig",
    ) -> ApplicationSession:
        if not app_info.executable:
            raise ApplicationLaunchException(
                app_name=app_info.name,
                executable="<none>",
                reason="executable is required for launch_application",
            )
        try:
            from pywinauto import Application  # type: ignore[import]
        except ImportError as exc:
            raise ApplicationLaunchException(
                app_name=app_info.name,
                executable=app_info.executable,
                reason="pywinauto is not installed. Run: pip install pywinauto",
                original_error=exc,
            ) from exc

        _log.info("launching_application", name=app_info.name, executable=app_info.executable)
        cmd = app_info.executable
        if app_info.launch_arguments:
            cmd += " " + " ".join(app_info.launch_arguments)

        try:
            pwa_app = Application(backend=self._backend).start(cmd)
        except Exception as exc:
            raise ApplicationLaunchException(
                app_name=app_info.name,
                executable=app_info.executable,
                reason=str(exc),
                original_error=exc,
            ) from exc

        timeout = config.application.launch_timeout_seconds
        main_window = self._wait_for_window(pwa_app, app_info, timeout)

        session = ApplicationSession(
            app_info=app_info,
            adapter_type=AdapterType.PYWINAUTO,
            native_session={
                "app": pwa_app,
                "main_window": main_window,
                "backend": self._backend,
            },
        )
        _log.info("application_launched", name=app_info.name, session=session.session_id)
        return session

    def attach_application(
        self,
        process_id: int,
        app_info: ApplicationInfo,
    ) -> ApplicationSession:
        try:
            from pywinauto import Application  # type: ignore[import]
        except ImportError as exc:
            raise ApplicationNotFoundException(
                identifier=str(process_id),
                reason="pywinauto is not installed. Run: pip install pywinauto",
            ) from exc

        try:
            pwa_app = Application(backend=self._backend).connect(process=process_id)
            main_window = pwa_app.top_window()
            session = ApplicationSession(
                app_info=app_info,
                adapter_type=AdapterType.PYWINAUTO,
                native_session={
                    "app": pwa_app,
                    "main_window": main_window,
                    "backend": self._backend,
                },
            )
            _log.info("application_attached", pid=process_id)
            return session
        except Exception as exc:
            raise ApplicationNotFoundException(
                identifier=str(process_id),
                reason=str(exc),
                original_error=exc,
            ) from exc

    def close_application(self, session: ApplicationSession) -> None:
        native = self._native(session)
        try:
            app = native.get("app")
            if app:
                app.kill()
            session.state = SessionState.CLOSED
            _log.info("application_closed")
        except Exception as exc:
            _log.warning("close_application_error", error=str(exc))
            session.state = SessionState.CLOSED

    # ------------------------------------------------------------------
    # Mouse interactions
    # ------------------------------------------------------------------

    def click(
        self, locator: UnifiedLocator, session: ApplicationSession, **kwargs: Any
    ) -> ActionResult:
        return self._execute_with_fallback(
            "click",
            lambda loc: lambda: self._find(session, loc).click_input(),
            locator,
            session,
        )

    def double_click(
        self, locator: UnifiedLocator, session: ApplicationSession, **kwargs: Any
    ) -> ActionResult:
        return self._execute_with_fallback(
            "double_click",
            lambda loc: lambda: self._find(session, loc).double_click_input(),
            locator,
            session,
        )

    def right_click(
        self, locator: UnifiedLocator, session: ApplicationSession, **kwargs: Any
    ) -> ActionResult:
        return self._execute_with_fallback(
            "right_click",
            lambda loc: lambda: self._find(session, loc).right_click_input(),
            locator,
            session,
        )

    def drag_and_drop(
        self,
        source: UnifiedLocator,
        target: UnifiedLocator,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> ActionResult:
        def _do() -> None:
            from pywinauto import mouse  # type: ignore[import]
            src_el = self._find(session, source.primary)
            tgt_el = self._find(session, target.primary)
            src_rect = src_el.rectangle()
            tgt_rect = tgt_el.rectangle()
            mouse.press(coords=(src_rect.mid_point()))
            time.sleep(0.1)
            mouse.release(coords=(tgt_rect.mid_point()))

        return self._execute_action("drag_and_drop", _do, session)

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def input_text(
        self,
        locator: UnifiedLocator,
        text: str,
        session: ApplicationSession,
        clear_first: bool = True,
        **kwargs: Any,
    ) -> ActionResult:
        def _do(loc: LocatorDefinition) -> Any:
            def _inner() -> None:
                el = self._find(session, loc)
                if clear_first:
                    el.set_text("")
                el.type_keys(text, with_spaces=True)
            return _inner

        return self._execute_with_fallback("input_text", _do, locator, session)

    def send_keys(
        self,
        locator: UnifiedLocator,
        keys: str,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> ActionResult:
        return self._execute_with_fallback(
            "send_keys",
            lambda loc: lambda: self._find(session, loc).type_keys(keys),
            locator,
            session,
        )

    def clear_text(
        self,
        locator: UnifiedLocator,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> ActionResult:
        return self._execute_with_fallback(
            "clear_text",
            lambda loc: lambda: self._find(session, loc).set_text(""),
            locator,
            session,
        )

    # ------------------------------------------------------------------
    # Element inspection
    # ------------------------------------------------------------------

    def get_text(
        self, locator: UnifiedLocator, session: ApplicationSession, **kwargs: Any
    ) -> str:
        for loc_def in locator.all_strategies():
            try:
                el = self._resolver.find_element(
                    self._native(session)["main_window"], loc_def,
                    timeout_seconds=loc_def.timeout or self._config.execution.timeout,
                )
                text = el.window_text()
                return text if text is not None else ""
            except Exception:
                continue
        raise ElementNotFoundException(locator_name=locator.name, strategies_tried=[
            loc.strategy.value for loc in locator.all_strategies()
        ])

    def get_element_attribute(
        self,
        locator: UnifiedLocator,
        attribute: str,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> str | None:
        for loc_def in locator.all_strategies():
            try:
                el = self._resolver.find_element(
                    self._native(session)["main_window"], loc_def,
                    timeout_seconds=loc_def.timeout or self._config.execution.timeout,
                )
                return str(getattr(el, attribute, None))
            except Exception:
                continue
        return None

    def element_exists(
        self,
        locator: UnifiedLocator,
        session: ApplicationSession,
        timeout: float = 3.0,
        **kwargs: Any,
    ) -> bool:
        for loc_def in locator.all_strategies():
            if self._resolver.element_exists(
                self._native(session)["main_window"], loc_def, timeout_seconds=timeout
            ):
                return True
        return False

    def wait_for_element(
        self,
        locator: UnifiedLocator,
        session: ApplicationSession,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> ActionResult:
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            if self.element_exists(locator, session, timeout=1.0):
                return ActionResult(action="wait_for_element", status=ActionStatus.SUCCESS,
                                    duration_ms=(time.monotonic() - start) * 1000)
            time.sleep(0.5)
        return ActionResult(action="wait_for_element", status=ActionStatus.TIMEOUT,
                            duration_ms=timeout * 1000,
                            error_message=f"Element '{locator.name}' did not appear in {timeout}s")

    def select_item(
        self,
        locator: UnifiedLocator,
        item: str,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> ActionResult:
        return self._execute_with_fallback(
            "select_item",
            lambda loc: lambda: self._find(session, loc).select(item),
            locator,
            session,
        )

    # ------------------------------------------------------------------
    # Window management
    # ------------------------------------------------------------------

    def _native_maximize_window(
        self, session: ApplicationSession, window_title: str | None
    ) -> None:
        win = self._get_window(session, window_title)
        win.maximize()

    def _native_minimize_window(
        self, session: ApplicationSession, window_title: str | None
    ) -> None:
        win = self._get_window(session, window_title)
        win.minimize()

    def switch_window(
        self,
        window_title: str,
        session: ApplicationSession,
        timeout: float = 10.0,
        **kwargs: Any,
    ) -> ActionResult:
        def _do() -> None:
            native = self._native(session)
            app = native["app"]
            win = app.window(title_re=f".*{window_title}.*")
            win.wait("exists visible", timeout=timeout)
            win.set_focus()
            native["main_window"] = win

        return self._execute_action("switch_window", _do, session)

    # ------------------------------------------------------------------
    # Screenshot
    # ------------------------------------------------------------------

    def take_screenshot(
        self,
        session: ApplicationSession,
        filename: str | None = None,
        **kwargs: Any,
    ) -> str:
        return self._screenshot_manager.capture(
            session=session, filename=filename
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _native(session: ApplicationSession) -> dict[str, Any]:
        if not isinstance(session.native_session, dict):
            raise RuntimeError(
                f"pywinauto native session expected dict, got {type(session.native_session)}"
            )
        return session.native_session

    def _find(self, session: ApplicationSession, loc_def: LocatorDefinition) -> Any:
        timeout = loc_def.timeout or self._config.execution.timeout
        return self._resolver.find_element(
            self._native(session)["main_window"], loc_def, timeout_seconds=timeout
        )

    def _get_window(self, session: ApplicationSession, title: str | None) -> Any:
        native = self._native(session)
        if title:
            return native["app"].window(title_re=f".*{title}.*")
        return native["main_window"]

    @staticmethod
    def _wait_for_window(pwa_app: Any, app_info: ApplicationInfo, timeout: float) -> Any:
        from pywinauto.timings import TimeoutError as PwaTimeout  # type: ignore[import]
        deadline = time.monotonic() + timeout
        title_hint = app_info.window_title or app_info.name or ""
        while time.monotonic() < deadline:
            try:
                if title_hint:
                    win = pwa_app.window(title_re=f".*{title_hint}.*")
                    win.wait("exists visible", timeout=2)
                    return win
                else:
                    return pwa_app.top_window()
            except Exception:
                time.sleep(0.5)
        raise ApplicationLaunchException(
            app_name=app_info.name,
            executable=app_info.executable or "<unknown>",
            reason=f"Main window did not appear within {timeout}s",
        )
