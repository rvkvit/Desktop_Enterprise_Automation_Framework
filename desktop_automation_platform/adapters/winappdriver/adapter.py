"""
WinAppDriverAdapter — IApplicationAdapter via Appium/WinAppDriver WebDriver protocol.

WinAppDriver (WAD) is Microsoft's open-source WebDriver server for Windows apps.
It implements the Appium protocol and supports:
  WPF · WinForms · WinUI3 · UWP · Win32 · Classic Desktop

Prerequisites
-------------
1. Download and install WinAppDriver from:
   https://github.com/microsoft/WinAppDriver/releases
2. Enable Developer Mode in Windows Settings
3. Start WinAppDriver.exe (runs on http://127.0.0.1:4723 by default)
4. pip install Appium-Python-Client

Config
------
In config.yaml::

    adapters:
      winappdriver:
        server_url: "http://127.0.0.1:4723"   # default
        platform_name: "Windows"
        device_name: "WindowsPC"

Session state
-------------
``session.native_session`` dict keys:
    "driver"       → appium.webdriver.Remote instance
    "server_url"   → WAD server URL
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from desktop_automation_platform.adapters.base_adapter import BaseDesktopAdapter
from desktop_automation_platform.adapters.winappdriver.element_resolver import (
    WinAppDriverElementResolver,
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

_DEFAULT_SERVER = "http://127.0.0.1:4723"


def _is_wad_available() -> bool:
    try:
        from appium import webdriver  # noqa: F401
        return True
    except ImportError:
        return False


class WinAppDriverAdapter(BaseDesktopAdapter):
    """Full IApplicationAdapter backed by WinAppDriver (Appium protocol)."""

    def __init__(
        self,
        config: "PlatformConfig",
        screenshot_manager: "IScreenshotManager",
    ) -> None:
        super().__init__(config=config, screenshot_manager=screenshot_manager)
        wad_cfg = getattr(getattr(config, "adapters", None), "winappdriver", None)
        self._server_url: str = getattr(wad_cfg, "server_url", _DEFAULT_SERVER)
        self._platform_name: str = getattr(wad_cfg, "platform_name", "Windows")
        self._device_name: str = getattr(wad_cfg, "device_name", "WindowsPC")
        self._resolver = WinAppDriverElementResolver()

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.WINAPPDRIVER

    @property
    def supported_technologies(self) -> list[ApplicationTechnology]:
        return [
            ApplicationTechnology.WPF,
            ApplicationTechnology.WINFORMS,
            ApplicationTechnology.WINUI3,
            ApplicationTechnology.WIN32,
            ApplicationTechnology.UWP,
            ApplicationTechnology.PACKAGED,
        ]

    def is_available(self) -> bool:
        return _is_wad_available()

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
                reason="executable is required",
            )
        try:
            from appium import webdriver  # type: ignore[import]
            from appium.options import AppiumOptions  # type: ignore[import]
        except ImportError as exc:
            raise ApplicationLaunchException(
                app_name=app_info.name,
                executable=app_info.executable,
                reason="Appium-Python-Client not installed. Run: pip install Appium-Python-Client",
                original_error=exc,
            ) from exc

        _log.info("wad_launching", name=app_info.name, executable=app_info.executable)

        options = AppiumOptions()
        options.platform_name = self._platform_name
        options.set_capability("app", app_info.executable)
        options.set_capability("deviceName", self._device_name)
        if app_info.working_directory:
            options.set_capability("appWorkingDir", app_info.working_directory)

        try:
            driver = webdriver.Remote(
                command_executor=self._server_url,
                options=options,
            )
        except Exception as exc:
            raise ApplicationLaunchException(
                app_name=app_info.name,
                executable=app_info.executable,
                reason=(
                    f"Failed to connect to WinAppDriver at {self._server_url}: {exc}. "
                    "Ensure WinAppDriver.exe is running and Developer Mode is enabled."
                ),
                original_error=exc,
            ) from exc

        session = ApplicationSession(
            app_info=app_info,
            adapter_type=AdapterType.WINAPPDRIVER,
            native_session={"driver": driver, "server_url": self._server_url},
        )
        _log.info("wad_launched", name=app_info.name, session=session.session_id)
        return session

    def attach_application(
        self,
        process_id: int,
        app_info: ApplicationInfo,
    ) -> ApplicationSession:
        try:
            from appium import webdriver  # type: ignore[import]
            from appium.options import AppiumOptions  # type: ignore[import]
        except ImportError as exc:
            raise ApplicationNotFoundException(
                identifier=str(process_id),
                reason="Appium-Python-Client not installed",
            ) from exc

        options = AppiumOptions()
        options.platform_name = self._platform_name
        options.set_capability("app", "Root")   # attach to running session via root
        options.set_capability("deviceName", self._device_name)

        try:
            driver = webdriver.Remote(
                command_executor=self._server_url,
                options=options,
            )
            session = ApplicationSession(
                app_info=app_info,
                adapter_type=AdapterType.WINAPPDRIVER,
                native_session={"driver": driver, "server_url": self._server_url},
            )
            _log.info("wad_attached", pid=process_id)
            return session
        except Exception as exc:
            raise ApplicationNotFoundException(
                identifier=str(process_id),
                reason=str(exc),
                original_error=exc,
            ) from exc

    def close_application(self, session: ApplicationSession) -> None:
        driver = self._driver(session)
        try:
            driver.quit()
            session.state = SessionState.CLOSED
            _log.info("wad_closed")
        except Exception as exc:
            _log.warning("wad_close_error", error=str(exc))
            session.state = SessionState.CLOSED

    # ------------------------------------------------------------------
    # Mouse interactions
    # ------------------------------------------------------------------

    def click(
        self, locator: UnifiedLocator, session: ApplicationSession, **kwargs: Any
    ) -> ActionResult:
        return self._execute_with_fallback(
            "click",
            lambda loc: lambda: self._find(session, loc).click(),
            locator,
            session,
        )

    def double_click(
        self, locator: UnifiedLocator, session: ApplicationSession, **kwargs: Any
    ) -> ActionResult:
        from selenium.webdriver.common.action_chains import ActionChains  # type: ignore[import]
        return self._execute_with_fallback(
            "double_click",
            lambda loc: lambda: ActionChains(self._driver(session))
                .double_click(self._find(session, loc)).perform(),
            locator,
            session,
        )

    def right_click(
        self, locator: UnifiedLocator, session: ApplicationSession, **kwargs: Any
    ) -> ActionResult:
        from selenium.webdriver.common.action_chains import ActionChains  # type: ignore[import]
        return self._execute_with_fallback(
            "right_click",
            lambda loc: lambda: ActionChains(self._driver(session))
                .context_click(self._find(session, loc)).perform(),
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
        from selenium.webdriver.common.action_chains import ActionChains  # type: ignore[import]

        def _do() -> None:
            driver = self._driver(session)
            src_el = self._find(session, source.primary)
            tgt_el = self._find(session, target.primary)
            ActionChains(driver).drag_and_drop(src_el, tgt_el).perform()

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
                    el.clear()
                el.send_keys(text)
            return _inner

        return self._execute_with_fallback("input_text", _do, locator, session)

    def send_keys(
        self,
        locator: UnifiedLocator,
        keys: str,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> ActionResult:
        # Translate Robot Framework key syntax to Selenium Keys
        translated = self._translate_keys(keys)
        return self._execute_with_fallback(
            "send_keys",
            lambda loc: lambda: self._find(session, loc).send_keys(translated),
            locator,
            session,
        )

    def clear_text(
        self, locator: UnifiedLocator, session: ApplicationSession, **kwargs: Any
    ) -> ActionResult:
        return self._execute_with_fallback(
            "clear_text",
            lambda loc: lambda: self._find(session, loc).clear(),
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
                el = self._resolver.find_element(self._driver(session), loc_def)
                return el.text or el.get_attribute("Value.Value") or ""
            except Exception:
                continue
        raise ElementNotFoundException(locator_name=locator.name, strategies_tried=[
            l.strategy.value for l in locator.all_strategies()
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
                el = self._resolver.find_element(self._driver(session), loc_def)
                return el.get_attribute(attribute)
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
            if self._resolver.element_exists(self._driver(session), loc_def, timeout):
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
                            error_message=f"Element '{locator.name}' not found in {timeout}s")

    def select_item(
        self,
        locator: UnifiedLocator,
        item: str,
        session: ApplicationSession,
        **kwargs: Any,
    ) -> ActionResult:
        from selenium.webdriver.support.ui import Select  # type: ignore[import]

        def _do(loc: LocatorDefinition) -> Any:
            def _inner() -> None:
                el = self._find(session, loc)
                try:
                    Select(el).select_by_visible_text(item)
                except Exception:
                    # Fallback: find the item by text within a list/combo
                    el.find_element("name", item).click()
            return _inner

        return self._execute_with_fallback("select_item", _do, locator, session)

    # ------------------------------------------------------------------
    # Window management
    # ------------------------------------------------------------------

    def _native_maximize_window(
        self, session: ApplicationSession, window_title: str | None
    ) -> None:
        self._driver(session).maximize_window()

    def _native_minimize_window(
        self, session: ApplicationSession, window_title: str | None
    ) -> None:
        from selenium.webdriver.common.keys import Keys  # type: ignore[import]
        from selenium.webdriver.common.action_chains import ActionChains  # type: ignore[import]
        ActionChains(self._driver(session)).send_keys(Keys.META + Keys.DOWN).perform()

    def switch_window(
        self,
        window_title: str,
        session: ApplicationSession,
        timeout: float = 10.0,
        **kwargs: Any,
    ) -> ActionResult:
        def _do() -> None:
            driver = self._driver(session)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                for handle in driver.window_handles:
                    driver.switch_to.window(handle)
                    if window_title.lower() in driver.title.lower():
                        return
                time.sleep(0.5)
            raise RuntimeError(f"Window '{window_title}' not found within {timeout}s")

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
        path = self._screenshot_manager.capture(session=session, filename=filename)
        try:
            # Also save via Appium (full window capture)
            self._driver(session).save_screenshot(path)
        except Exception:
            pass
        return path

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _driver(self, session: ApplicationSession) -> Any:
        native = session.native_session
        if not isinstance(native, dict):
            raise RuntimeError("WinAppDriver native session expected dict")
        return native["driver"]

    def _find(self, session: ApplicationSession, loc_def: LocatorDefinition) -> Any:
        timeout = loc_def.timeout or self._config.execution.timeout
        return self._resolver.find_element(self._driver(session), loc_def, timeout)

    @staticmethod
    def _translate_keys(keys: str) -> str:
        """Translate {ENTER}, {TAB} etc. to Selenium Keys constants."""
        from selenium.webdriver.common.keys import Keys  # type: ignore[import]
        _MAP = {
            "{ENTER}": Keys.ENTER, "{TAB}": Keys.TAB, "{ESC}": Keys.ESCAPE,
            "{ESCAPE}": Keys.ESCAPE, "{F5}": Keys.F5, "{DELETE}": Keys.DELETE,
            "{BACKSPACE}": Keys.BACKSPACE, "{HOME}": Keys.HOME, "{END}": Keys.END,
            "{UP}": Keys.UP, "{DOWN}": Keys.DOWN, "{LEFT}": Keys.LEFT, "{RIGHT}": Keys.RIGHT,
            "{CTRL}": Keys.CONTROL, "{ALT}": Keys.ALT, "{SHIFT}": Keys.SHIFT,
        }
        result = keys
        for token, key in _MAP.items():
            result = result.replace(token, key)
        return result
