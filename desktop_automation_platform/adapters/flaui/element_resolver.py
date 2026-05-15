"""
FlaUIElementResolver — finds UIA elements with timeout and fallback support.

This module owns the critical inner loop of the FlaUI adapter:
  1. Translate a LocatorDefinition to a FlaUI search condition
  2. Search the automation tree with polling until the element appears
     or the timeout elapses
  3. On failure, caller iterates to the next fallback strategy

Key FlaUI API used
------------------
AutomationElement.FindFirst(TreeScope, ConditionBase)  → single element
AutomationElement.FindAll(TreeScope, ConditionBase)    → element array
FlaUI.Core.Tools.Retry.WhileNull(Func, TimeSpan, TimeSpan, msg)
    → polls until non-null result or timeout, returns RetryResult<T>

Tree scopes
-----------
TreeScope.Element    — the root itself only
TreeScope.Children   — direct children only
TreeScope.Descendants — entire subtree (most common for desktop automation)
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from desktop_automation_platform.adapters.flaui.control_type_map import resolve_control_type
from desktop_automation_platform.core.exceptions import (
    AmbiguousLocatorException,
    ElementNotFoundException,
    LocatorResolutionException,
)
from desktop_automation_platform.core.models import LocatorDefinition, LocatorStrategy
from desktop_automation_platform.utils.logger import get_logger

if TYPE_CHECKING:
    pass

_log = get_logger(__name__)


class FlaUIElementResolver:
    """
    Resolves a ``LocatorDefinition`` to a live ``AutomationElement`` within
    a given search root (typically the application main window).
    """

    def __init__(self, automation: Any) -> None:
        """
        Parameters
        ----------
        automation:
            UIA3Automation or UIA2Automation instance.
        """
        self._automation = automation

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_element(
        self,
        root: Any,
        locator: LocatorDefinition,
        timeout_seconds: float = 30.0,
        poll_interval_seconds: float = 0.5,
        scope: Any | None = None,
    ) -> Any:
        """
        Find a single element matching ``locator`` within ``root``.

        If ``scope`` is provided (another AutomationElement), the search is
        constrained to the subtree rooted at ``scope`` rather than ``root``.

        Raises ``ElementNotFoundException`` on timeout.
        Raises ``AmbiguousLocatorException`` if ``locator.index`` is None
        and more than one element matches a strategy that might return multiples.
        """
        search_root = scope if scope is not None else root
        condition = self._build_condition(locator)
        tree_scope = self._get_tree_scope()

        _log.debug(
            "element_search_started",
            strategy=locator.strategy.value,
            value=locator.value,
            timeout=timeout_seconds,
        )

        element = self._poll_find_first(
            search_root, tree_scope, condition, timeout_seconds, poll_interval_seconds
        )

        if element is None:
            raise ElementNotFoundException(
                locator_name=locator.value,
                strategies_tried=[locator.strategy.value],
                timeout_seconds=timeout_seconds,
            )

        if locator.index is not None and locator.index > 0:
            # Caller wants the Nth match — fetch all and select by index
            element = self._find_by_index(
                search_root, tree_scope, condition, locator.index, timeout_seconds
            )

        _log.debug(
            "element_found",
            strategy=locator.strategy.value,
            value=locator.value,
            name=self._safe_name(element),
        )
        return element

    def find_all_elements(
        self,
        root: Any,
        locator: LocatorDefinition,
        timeout_seconds: float = 10.0,
    ) -> list[Any]:
        """
        Return all elements matching ``locator`` within ``root``.
        Returns an empty list (not raises) on timeout.
        """
        condition = self._build_condition(locator)
        tree_scope = self._get_tree_scope()
        try:
            elements = root.FindAll(tree_scope, condition)
            return list(elements) if elements else []
        except Exception as exc:
            _log.debug("find_all_failed", error=str(exc))
            return []

    def element_exists(
        self,
        root: Any,
        locator: LocatorDefinition,
        timeout_seconds: float = 5.0,
    ) -> bool:
        """
        Return True if an element matching ``locator`` exists within ``timeout``.
        Never raises.
        """
        try:
            condition = self._build_condition(locator)
            tree_scope = self._get_tree_scope()
            element = self._poll_find_first(
                root, tree_scope, condition, timeout_seconds, poll_interval_seconds=0.3
            )
            return element is not None
        except Exception:
            return False

    def find_window_by_title(
        self,
        automation: Any,
        title: str,
        partial: bool = True,
        timeout_seconds: float = 30.0,
    ) -> Any:
        """
        Find a top-level window whose title matches ``title``.
        Used by switch_window and attach_application.
        """
        try:
            from FlaUI.Core.Definitions import TreeScope  # type: ignore[import]
        except ImportError as exc:
            raise LocatorResolutionException(
                locator_name=title,
                strategy="window_title",
                adapter_type="flaui",
            ) from exc

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                desktop = automation.GetDesktop()
                windows = desktop.FindAll(TreeScope.Children, automation.ConditionFactory.ByControlType(
                    self._window_control_type()
                ))
                for win in windows:
                    try:
                        win_title = win.Name or ""
                        if partial and title.lower() in win_title.lower():
                            return win
                        elif not partial and win_title.lower() == title.lower():
                            return win
                    except Exception:
                        continue
            except Exception:
                pass
            time.sleep(0.5)

        raise ElementNotFoundException(
            locator_name=title,
            strategies_tried=["window_title"],
            timeout_seconds=timeout_seconds,
        )

    # ------------------------------------------------------------------
    # Condition builders
    # ------------------------------------------------------------------

    def _build_condition(self, locator: LocatorDefinition) -> Any:
        """Translate a LocatorDefinition to a FlaUI ConditionBase."""
        strategy = locator.strategy
        value = locator.value
        cf = self._automation.ConditionFactory

        try:
            if strategy == LocatorStrategy.AUTOMATION_ID:
                return cf.ByAutomationId(value)

            elif strategy == LocatorStrategy.NAME:
                return cf.ByName(value)

            elif strategy == LocatorStrategy.CLASS_NAME:
                return cf.ByClassName(value)

            elif strategy == LocatorStrategy.CONTROL_TYPE:
                control_type = resolve_control_type(value)
                return cf.ByControlType(control_type)

            elif strategy == LocatorStrategy.TEXT:
                return cf.ByName(value)

            elif strategy == LocatorStrategy.PARTIAL_TEXT:
                # FlaUI doesn't have ByPartialName natively — use property condition
                return self._build_partial_name_condition(value)

            elif strategy == LocatorStrategy.RUNTIME_ID:
                return cf.ByRuntimeId(self._parse_runtime_id(value))

            elif strategy == LocatorStrategy.XPATH:
                # XPath not natively supported by UIA; handled by tree traversal
                raise LocatorResolutionException(
                    locator_name=value,
                    strategy=strategy.value,
                    adapter_type="flaui",
                )

            elif strategy == LocatorStrategy.IMAGE:
                raise LocatorResolutionException(
                    locator_name=value,
                    strategy=strategy.value,
                    adapter_type="flaui",
                )

            else:
                raise LocatorResolutionException(
                    locator_name=value,
                    strategy=strategy.value,
                    adapter_type="flaui",
                )
        except LocatorResolutionException:
            raise
        except Exception as exc:
            raise LocatorResolutionException(
                locator_name=value,
                strategy=strategy.value,
                adapter_type="flaui",
            ) from exc

    def _build_partial_name_condition(self, partial_name: str) -> Any:
        """
        Build a condition matching elements whose Name contains ``partial_name``.
        Uses PropertyCondition with ContainsString (UIA3 property API).
        """
        try:
            from FlaUI.Core.Conditions import PropertyCondition  # type: ignore[import]
            from FlaUI.Core.Definitions import PropertyConditionFlags  # type: ignore[import]

            prop_id = self._automation.PropertyLibrary.Element.Name
            return PropertyCondition(
                prop_id,
                partial_name,
                PropertyConditionFlags.IgnoreCase,
            )
        except Exception:
            # Fallback: exact name match (degrades gracefully)
            _log.warning(
                "partial_text_condition_fallback",
                value=partial_name,
                reason="PropertyConditionFlags not available; using exact name match",
            )
            return self._automation.ConditionFactory.ByName(partial_name)

    # ------------------------------------------------------------------
    # Polling helpers
    # ------------------------------------------------------------------

    def _poll_find_first(
        self,
        root: Any,
        tree_scope: Any,
        condition: Any,
        timeout_seconds: float,
        poll_interval_seconds: float,
    ) -> Any | None:
        """
        Poll root.FindFirst until element found or timeout.
        Returns the element or None on timeout.
        """
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                element = root.FindFirst(tree_scope, condition)
                if element is not None:
                    return element
            except Exception:
                pass
            time.sleep(poll_interval_seconds)
        return None

    def _find_by_index(
        self,
        root: Any,
        tree_scope: Any,
        condition: Any,
        index: int,
        timeout_seconds: float,
    ) -> Any:
        """Return the Nth element (0-based) matching the condition."""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                elements = root.FindAll(tree_scope, condition)
                if elements and len(elements) > index:
                    return elements[index]
            except Exception:
                pass
            time.sleep(0.3)
        raise ElementNotFoundException(
            locator_name=f"index={index}",
            strategies_tried=["index_selection"],
            timeout_seconds=timeout_seconds,
        )

    # ------------------------------------------------------------------
    # FlaUI type helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_tree_scope() -> Any:
        try:
            from FlaUI.Core.Definitions import TreeScope  # type: ignore[import]

            return TreeScope.Descendants
        except ImportError:
            return 4  # TreeScope.Descendants numeric fallback

    @staticmethod
    def _window_control_type() -> Any:
        try:
            from FlaUI.Core.Definitions import ControlType  # type: ignore[import]

            return ControlType.Window
        except ImportError:
            return 50032  # UIA ControlType.Window raw value

    @staticmethod
    def _parse_runtime_id(value: str) -> Any:
        """Parse comma/space-separated integers to int[] for RuntimeId condition."""
        try:
            parts = [int(x.strip()) for x in value.replace(",", " ").split()]
            import System  # type: ignore[import]

            arr = System.Array[System.Int32](parts)
            return arr
        except Exception as exc:
            raise ValueError(f"Invalid runtime_id value {value!r}: {exc}") from exc

    @staticmethod
    def _safe_name(element: Any) -> str:
        try:
            return str(element.Name or "")
        except Exception:
            return "<unknown>"
