"""
DesktopAutomationLibrary — Robot Framework keyword library.

Maps Robot Framework keywords to the platform's unified adapter interface.
One instance is created per test suite (ROBOT_LIBRARY_SCOPE = "SUITE").
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from robot.api import logger as robot_logger

from desktop_automation_platform.core.container import bootstrap
from desktop_automation_platform.core.exceptions import PlatformException
from desktop_automation_platform.core.models import (
    ActionStatus,
    ApplicationInfo,
    ApplicationSession,
    UnifiedLocator,
)
from desktop_automation_platform.locator_engine.locator_model import LocatorRepository
from desktop_automation_platform.utils.logger import get_logger

_log = get_logger(__name__)


class DesktopAutomationLibrary:
    """
    Robot Framework library for automating Windows desktop applications.

    Supports WPF, WinForms, WinUI3, MAUI, Win32, Java Swing, Electron, Citrix/RDP.
    Technology is auto-detected by default.

    Import with the paths to your config and locators files:

    | Library | DesktopAutomationLibrary | config_path=config.yaml | locator_path=locators.yaml |
    """

    ROBOT_LIBRARY_SCOPE = "SUITE"
    ROBOT_LIBRARY_VERSION = "1.0.0"
    ROBOT_LIBRARY_DOC_FORMAT = "HTML"

    def __init__(
        self,
        config_path: str = "config.yaml",
        locator_path: str | None = None,
        healing_report: bool = True,
    ) -> None:
        self._config_path = str(Path(config_path).resolve())
        self._locator_path = str(Path(locator_path).resolve()) if locator_path else None
        self._healing_report = healing_report

        # Initialised by bootstrap()
        self._container = None
        self._adapter_manager = None
        self._platform_config = None
        self._locator_repo: LocatorRepository | None = None

        # Per-launch state
        self._session: ApplicationSession | None = None
        self._adapter = None

        self._bootstrap()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _bootstrap(self) -> None:
        container, manager = bootstrap(
            self._config_path,
            register_default_adapters=True,
        )
        self._container = container
        self._adapter_manager = manager

        # Grab the loaded config from the config manager
        from desktop_automation_platform.config.framework_config import YamlConfigManager
        cfg_manager: YamlConfigManager = container.config_manager()
        self._platform_config = cfg_manager.load(self._config_path)

        if self._locator_path:
            lp = Path(self._locator_path)
            if lp.is_dir():
                self._locator_repo = LocatorRepository.from_directory(lp)
            else:
                self._locator_repo = LocatorRepository.from_yaml(lp)

        if self._healing_report:
            try:
                from desktop_automation_platform.recovery.robot_listener import HealingListener
                from robot.libraries.BuiltIn import BuiltIn
                BuiltIn().import_library(
                    "desktop_automation_platform.recovery.robot_listener.HealingListener"
                )
            except Exception:
                pass  # Outside Robot context (e.g. libdoc) — skip listener registration

        robot_logger.info(
            f"DesktopAutomationLibrary initialised "
            f"(config={self._config_path}, locators={self._locator_path})"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_locator(self, locator_name: str) -> UnifiedLocator:
        if self._locator_repo is None:
            raise RuntimeError(
                "No locator repository loaded. "
                "Pass locator_path= when importing the library."
            )
        return self._locator_repo.get(locator_name)

    def _require_session(self) -> ApplicationSession:
        if self._session is None:
            raise RuntimeError(
                "No active application session. "
                "Call 'Launch Application' or 'Attach Application' first."
            )
        return self._session

    def _require_adapter(self):
        if self._adapter is None:
            raise RuntimeError(
                "No adapter is active. "
                "Call 'Launch Application' or 'Attach Application' first."
            )
        return self._adapter

    def _check(self, result) -> None:
        if not result.is_success():
            msg = f"[{result.action}] FAILED: {result.error_message}"
            if result.screenshot_path:
                robot_logger.info(f"Failure screenshot: {result.screenshot_path}")
            raise AssertionError(msg)
        robot_logger.debug(f"[{result.action}] OK ({result.duration_ms:.0f} ms)")

    # ------------------------------------------------------------------
    # Application lifecycle
    # ------------------------------------------------------------------

    def launch_application(
        self,
        config_path: str | None = None,
        locator_path: str | None = None,
    ) -> None:
        """Launch the desktop application defined in ``config.yaml``.

        Optionally override the config/locator paths set at import time.

        Examples:
        | Launch Application |
        | Launch Application | config_path=other.yaml |
        """
        if config_path:
            self._config_path = str(Path(config_path).resolve())
            self._bootstrap()
        if locator_path:
            self._locator_path = str(Path(locator_path).resolve())
            lp = Path(self._locator_path)
            if lp.is_dir():
                self._locator_repo = LocatorRepository.from_directory(lp)
            else:
                self._locator_repo = LocatorRepository.from_yaml(lp)

        cfg = self._platform_config
        app_info = ApplicationInfo(
            name=cfg.application.name,
            executable=cfg.application.executable,
            window_title=cfg.application.window_title,
            working_directory=cfg.application.working_directory,
            launch_arguments=list(cfg.application.launch_arguments),
            environment=dict(cfg.application.environment),
        )

        self._adapter = self._adapter_manager.resolve_adapter(app_info)
        self._session = self._adapter.launch_application(app_info, cfg)

        # Register in manager cache so get_adapter_for_session works too
        self._adapter_manager._session_adapters[self._session.session_id] = self._adapter

        robot_logger.info(
            f"Application launched: {cfg.application.name} "
            f"(session {self._session.session_id[:8]})"
        )

    def attach_application(self, process_id: int | str, app_name: str = "") -> None:
        """Attach to a running application by its Windows process ID.

        Examples:
        | Attach Application | 1234 |
        | Attach Application | 1234 | app_name=Claims Desktop |
        """
        pid = int(process_id)
        app_info = ApplicationInfo(name=app_name or f"PID:{pid}", process_id=pid)
        self._adapter = self._adapter_manager.resolve_adapter(app_info)
        self._session = self._adapter.attach_application(pid, app_info)
        self._adapter_manager._session_adapters[self._session.session_id] = self._adapter
        robot_logger.info(f"Attached to process {pid}")

    def close_application(self) -> None:
        """Close the application and end the session.

        Example:
        | Close Application |
        """
        if self._session is not None and self._adapter is not None:
            try:
                self._adapter.close_application(self._session)
                self._adapter_manager.release_session(self._session)
            except Exception as exc:
                robot_logger.warn(f"Error during close: {exc}")
            finally:
                self._session = None
                self._adapter = None
        robot_logger.info("Application closed.")

    # ------------------------------------------------------------------
    # Click operations
    # ------------------------------------------------------------------

    def click(self, locator: str, **kwargs: Any) -> None:
        """Left-click the element identified by ``locator``.

        Example:
        | Click | LOGIN_BUTTON |
        """
        loc = self._resolve_locator(locator)
        result = self._require_adapter().click(loc, self._require_session(), **kwargs)
        self._check(result)

    def double_click(self, locator: str, **kwargs: Any) -> None:
        """Double-click the element identified by ``locator``.

        Example:
        | Double Click | FILE_ICON |
        """
        loc = self._resolve_locator(locator)
        result = self._require_adapter().double_click(loc, self._require_session(), **kwargs)
        self._check(result)

    def right_click(self, locator: str, **kwargs: Any) -> None:
        """Right-click the element (opens context menu).

        Example:
        | Right Click | TABLE_ROW |
        """
        loc = self._resolve_locator(locator)
        result = self._require_adapter().right_click(loc, self._require_session(), **kwargs)
        self._check(result)

    def drag_and_drop(self, source_locator: str, target_locator: str, **kwargs: Any) -> None:
        """Drag ``source_locator`` and drop it onto ``target_locator``.

        Example:
        | Drag And Drop | TASK_CARD | DROP_ZONE |
        """
        source = self._resolve_locator(source_locator)
        target = self._resolve_locator(target_locator)
        result = self._require_adapter().drag_and_drop(
            source, target, self._require_session(), **kwargs
        )
        self._check(result)

    # ------------------------------------------------------------------
    # Text input
    # ------------------------------------------------------------------

    def input_text(
        self,
        locator: str,
        text: str,
        clear_first: bool = True,
        **kwargs: Any,
    ) -> None:
        """Type ``text`` into the field identified by ``locator``.

        Clears the field first by default (set ``clear_first=False`` to append).

        Examples:
        | Input Text | USERNAME_FIELD | john.doe@company.com |
        | Input Text | NOTES_FIELD | extra text | clear_first=False |
        """
        loc = self._resolve_locator(locator)
        result = self._require_adapter().input_text(
            loc, text, self._require_session(), clear_first=clear_first, **kwargs
        )
        self._check(result)

    def send_keys(self, locator: str, keys: str, **kwargs: Any) -> None:
        """Send keyboard keys to the element. Use ``{ENTER}``, ``{TAB}``, ``{F5}``, etc.

        Examples:
        | Send Keys | SEARCH_BOX | {ENTER} |
        | Send Keys | FORM | {CTRL}+{A} |
        """
        loc = self._resolve_locator(locator)
        result = self._require_adapter().send_keys(loc, keys, self._require_session(), **kwargs)
        self._check(result)

    def clear_text(self, locator: str, **kwargs: Any) -> None:
        """Clear all text from the field identified by ``locator``.

        Example:
        | Clear Text | SEARCH_BOX |
        """
        loc = self._resolve_locator(locator)
        result = self._require_adapter().clear_text(loc, self._require_session(), **kwargs)
        self._check(result)

    # ------------------------------------------------------------------
    # Element inspection
    # ------------------------------------------------------------------

    def get_text(self, locator: str, **kwargs: Any) -> str:
        """Return the visible text of the element identified by ``locator``.

        Example:
        | ${status}= | Get Text | STATUS_LABEL |
        | Should Contain | ${status} | Active |
        """
        loc = self._resolve_locator(locator)
        return self._require_adapter().get_text(loc, self._require_session(), **kwargs)

    def get_element_attribute(
        self, locator: str, attribute: str, **kwargs: Any
    ) -> str | None:
        """Return the value of a named attribute of the element.

        Common attributes: ``name``, ``automation_id``, ``class_name``,
        ``is_enabled``, ``is_offscreen``, ``value``.

        Example:
        | ${id}= | Get Element Attribute | LOGIN_BUTTON | automation_id |
        """
        loc = self._resolve_locator(locator)
        return self._require_adapter().get_element_attribute(
            loc, attribute, self._require_session(), **kwargs
        )

    def element_exists(self, locator: str, timeout: float = 3.0, **kwargs: Any) -> bool:
        """Return ``True`` if the element is present, ``False`` otherwise.

        Does NOT fail the test — safe to use in conditional logic.

        Example:
        | ${visible}= | Element Exists | ERROR_BANNER | timeout=2 |
        | Run Keyword If | ${visible} | Log | Error appeared |
        """
        loc = self._resolve_locator(locator)
        return self._require_adapter().element_exists(
            loc, self._require_session(), timeout=float(timeout), **kwargs
        )

    def wait_for_element(self, locator: str, timeout: float = 30.0, **kwargs: Any) -> None:
        """Wait until the element appears. Fails if it doesn't appear within ``timeout`` seconds.

        Example:
        | Wait For Element | DASHBOARD_TITLE | timeout=20 |
        """
        loc = self._resolve_locator(locator)
        result = self._require_adapter().wait_for_element(
            loc, self._require_session(), timeout=float(timeout), **kwargs
        )
        if result.status == ActionStatus.TIMEOUT:
            raise AssertionError(
                f"Element '{locator}' did not appear within {timeout} seconds."
            )

    def element_should_exist(
        self, locator: str, timeout: float = 10.0, msg: str = ""
    ) -> None:
        """Fail the test if the element does not exist within ``timeout`` seconds.

        Example:
        | Element Should Exist | SUCCESS_BANNER |
        | Element Should Exist | SAVE_BUTTON | timeout=5 | msg=Save button missing |
        """
        if not self.element_exists(locator, timeout=timeout):
            raise AssertionError(
                msg or f"Element '{locator}' was not found within {timeout} seconds."
            )

    def element_should_not_exist(
        self, locator: str, timeout: float = 3.0, msg: str = ""
    ) -> None:
        """Fail the test if the element IS present (it should be absent).

        Example:
        | Element Should Not Exist | ERROR_BANNER |
        """
        if self.element_exists(locator, timeout=timeout):
            raise AssertionError(
                msg or f"Element '{locator}' was found but should not be present."
            )

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def select_item(self, locator: str, item: str, **kwargs: Any) -> None:
        """Select an item from a dropdown / combo box / list by visible text.

        Example:
        | Select Item | CLAIM_TYPE_DROPDOWN | Medical |
        """
        loc = self._resolve_locator(locator)
        result = self._require_adapter().select_item(
            loc, item, self._require_session(), **kwargs
        )
        self._check(result)

    # ------------------------------------------------------------------
    # Window management
    # ------------------------------------------------------------------

    def maximize_window(self, window_title: str = "") -> None:
        """Maximise the application window.

        Example:
        | Maximize Window |
        """
        result = self._require_adapter().maximize_window(
            self._require_session(), window_title=window_title or None
        )
        self._check(result)

    def minimize_window(self, window_title: str = "") -> None:
        """Minimise the application window.

        Example:
        | Minimize Window |
        """
        result = self._require_adapter().minimize_window(
            self._require_session(), window_title=window_title or None
        )
        self._check(result)

    def switch_window(self, window_title: str, timeout: float = 10.0) -> None:
        """Switch focus to a window whose title contains ``window_title``.

        Examples:
        | Switch Window | Save As |
        | Switch Window | Confirm Delete | timeout=5 |
        """
        result = self._require_adapter().switch_window(
            window_title, self._require_session(), timeout=float(timeout)
        )
        self._check(result)

    # ------------------------------------------------------------------
    # Screenshot
    # ------------------------------------------------------------------

    def take_screenshot(self, filename: str = "") -> str:
        """Capture a screenshot and return the saved file path.

        Example:
        | Take Screenshot |
        | ${path}= | Take Screenshot | filename=login_screen |
        """
        path = self._require_adapter().take_screenshot(
            self._require_session(), filename=filename or None
        )
        robot_logger.info(f"Screenshot saved: {path}")
        return path

    # ------------------------------------------------------------------
    # Self-healing report (Phase 5)
    # ------------------------------------------------------------------

    def get_healing_report(self) -> str:
        """Return a human-readable self-healing summary for the current test run.

        Describes every locator that healed (fell back to a secondary strategy or
        was recovered by popup dismissal / stale window reattachment / fuzzy match)
        and recommends which locators should be updated in ``locators.yaml``.

        Call this at the end of a suite to review locator health:

        Examples:
        | ${report}= | Get Healing Report |
        | Log | ${report} |
        | Should Not Contain | ${report} | ACTION: |    # fail if any locator needs updating
        """
        from desktop_automation_platform.recovery import HealingTracker
        report = HealingTracker.instance().summary()
        robot_logger.info(report)
        return report

    # ------------------------------------------------------------------
    # Locator scanner (Phase 4)
    # ------------------------------------------------------------------

    def scan_application_screen(
        self,
        output_path: str = "scanned_locators.yaml",
        max_depth: int = 12,
        overwrite: bool = True,
        include_containers: bool = False,
        wait_seconds: float = 0,
        all_windows: bool = False,
        min_score: int = 40,
    ) -> str:
        """Scan the running application's UI tree and generate a locators.yaml file.

        Walks the live Windows UIA accessibility tree, scores every element for
        locator quality, and writes a ready-to-use ``locators.yaml`` to ``output_path``.

        For slow-loading applications (Office, OneNote, etc.) use ``wait_seconds``
        to let the application fully render before scanning.
        For complex applications use ``all_windows=True`` to scan every top-level
        window, not just the main window.

        Score key:
        | ★★★ | automation_id — developer-set, most stable        |
        | ★★  | name — accessible label or button caption          |
        | ★   | class_name — Win32 class, stable but less unique   |

        Examples:
        | Scan Application Screen |
        | Scan Application Screen | output_path=screens/login/locators.yaml |
        | Scan Application Screen | wait_seconds=5 | all_windows=True |
        | Scan Application Screen | max_depth=15 | min_score=20 |
        """
        import time

        from desktop_automation_platform.adapters.flaui.element_resolver import FlaUIElementResolver
        from desktop_automation_platform.adapters.flaui.scanner import FlaUILocatorScanner
        from desktop_automation_platform.scanner.locator_generator import LocatorGenerator
        from desktop_automation_platform.scanner.yaml_exporter import YamlExporter

        session = self._require_session()

        # Optional delay — let slow apps (Office, OneNote) finish rendering
        if float(wait_seconds) > 0:
            robot_logger.info(f"Waiting {wait_seconds}s for application to fully load...")
            time.sleep(float(wait_seconds))

        # Reuse the session's own automation instance so element tree-walking
        # works correctly — creating a new instance causes FindAll to return
        # no children for elements that belong to a different automation context.
        native = session.native_session if isinstance(session.native_session, dict) else {}
        automation = native.get("automation")
        flaui_app = native.get("application")

        if automation is None:
            from desktop_automation_platform.adapters.flaui.automation_factory import create_automation
            automation = create_automation("UIA3")
            robot_logger.warn(
                "Session has no stored automation instance — created a new one. "
                "Results may be incomplete for some applications."
            )

        # Re-find the current main window at scan time.
        # This handles apps that transition from a splash/loading window to the
        # real application window (e.g. Microsoft Word, Excel).
        current_window = native.get("main_window")
        if flaui_app is not None:
            try:
                fresh = flaui_app.GetMainWindow(automation)
                if fresh is not None:
                    current_window = fresh
                    native["main_window"] = current_window
                    robot_logger.info("Main window refreshed — using current application window.")
            except Exception as exc:
                robot_logger.warn(f"Could not refresh main window: {exc}. Using stored reference.")

        resolver = FlaUIElementResolver(automation)
        flaui_scanner = FlaUILocatorScanner(automation, resolver)

        all_elements: list = []

        if bool(all_windows) and flaui_app is not None:
            # Scan all top-level windows (better for Office, OneNote, multi-window apps)
            robot_logger.info("Scanning ALL top-level application windows...")
            try:
                windows = flaui_app.GetAllTopLevelWindows(automation)
                for win in windows:
                    try:
                        win_elements = flaui_scanner._walk_tree(
                            win, depth=0, max_depth=int(max_depth), parent_id=None
                        )
                        all_elements.extend(win_elements)
                        robot_logger.info(
                            f"  Window '{getattr(win, 'Name', '?')}': {len(win_elements)} elements"
                        )
                    except Exception as exc:
                        robot_logger.warn(f"  Could not scan window: {exc}")
            except Exception as exc:
                robot_logger.warn(f"GetAllTopLevelWindows failed: {exc}. Falling back to main window.")

        if not all_elements:
            # Standard single-window scan
            robot_logger.info(f"Scanning main window (max_depth={max_depth})...")
            all_elements = flaui_scanner.scan_application(session, max_depth=int(max_depth))

        robot_logger.info(
            f"Tree walk complete — {len(all_elements)} raw elements found. "
            f"Applying filters (min_score={min_score}, include_containers={include_containers})..."
        )

        if len(all_elements) == 0:
            robot_logger.warn(
                "No elements found in the UI tree. Possible causes:\n"
                "  1. The application is still loading — add wait_seconds=5 (or more)\n"
                "  2. The app uses a non-UIA technology — try adapter_mode: pywinauto in config.yaml\n"
                "  3. The application window is minimised or off-screen"
            )

        generator = LocatorGenerator(
            include_containers=bool(include_containers),
            include_invisible=False,
            min_score=int(min_score),
        )
        scored = generator.generate(all_elements)

        if len(scored) == 0 and len(all_elements) > 0:
            robot_logger.warn(
                f"All {len(all_elements)} elements were filtered out. Possible causes:\n"
                f"  1. Elements have no AutomationId, Name, or ClassName — try min_score=20\n"
                f"  2. All elements are off-screen — try include_containers=True\n"
                f"  3. App uses virtual/composed UI (modern Office, OneNote) — "
                f"try all_windows=True and wait_seconds=5"
            )

        exporter = YamlExporter()
        written_path = exporter.export(
            scored,
            output_path=output_path,
            overwrite=bool(overwrite),
            add_metadata=True,
        )

        summary = exporter.export_summary(scored)
        robot_logger.info(summary)
        robot_logger.info(f"Locators written to: {written_path}")
        return written_path
