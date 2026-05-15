"""
PywinautoElementResolver — finds UI elements using pywinauto's backend.

Supports both the ``uia`` backend (modern apps, recommended) and the
``win32`` backend (legacy Win32/MFC/VB6 applications).

Strategy mapping
----------------
  automation_id → auto_id
  name          → title / title_re (regex)
  class_name    → class_name
  control_type  → control_type (uia backend) / class_name (win32)
  xpath         → Not natively supported; falls back to name search
"""

from __future__ import annotations

import re
import time
from typing import Any

from desktop_automation_platform.core.models import LocatorDefinition, LocatorStrategy
from desktop_automation_platform.utils.logger import get_logger

_log = get_logger(__name__)


class PywinautoElementResolver:
    """Locates elements in a pywinauto window using UnifiedLocator strategies."""

    def __init__(self, backend: str = "uia") -> None:
        self._backend = backend

    def find_element(
        self,
        window: Any,
        loc_def: LocatorDefinition,
        timeout_seconds: float = 10.0,
    ) -> Any:
        """
        Return the pywinauto wrapper for the element described by ``loc_def``.
        Raises RuntimeError if the element is not found within the timeout.
        """
        strategy = loc_def.strategy
        value = str(loc_def.value)
        deadline = time.monotonic() + timeout_seconds

        while time.monotonic() < deadline:
            try:
                element = self._find_by_strategy(window, strategy, value)
                if element is not None:
                    return element
            except Exception:
                pass
            time.sleep(0.3)

        raise RuntimeError(
            f"Element not found: strategy={strategy.value}, value={value!r} "
            f"within {timeout_seconds}s"
        )

    def element_exists(
        self,
        window: Any,
        loc_def: LocatorDefinition,
        timeout_seconds: float = 3.0,
    ) -> bool:
        try:
            self.find_element(window, loc_def, timeout_seconds=timeout_seconds)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Strategy dispatch
    # ------------------------------------------------------------------

    def _find_by_strategy(
        self, window: Any, strategy: LocatorStrategy, value: str
    ) -> Any | None:
        if strategy == LocatorStrategy.AUTOMATION_ID:
            return self._find_by_auto_id(window, value)
        if strategy == LocatorStrategy.NAME:
            return self._find_by_name(window, value)
        if strategy == LocatorStrategy.CLASS_NAME:
            return self._find_by_class(window, value)
        if strategy == LocatorStrategy.CONTROL_TYPE:
            return self._find_by_control_type(window, value)
        if strategy == LocatorStrategy.XPATH:
            # pywinauto has no XPath — fall back to name search
            return self._find_by_name(window, value)
        return None

    def _find_by_auto_id(self, window: Any, auto_id: str) -> Any | None:
        try:
            wrapper = window.child_window(auto_id=auto_id)
            wrapper.wait("exists enabled", timeout=0.1)
            return wrapper
        except Exception:
            return None

    def _find_by_name(self, window: Any, name: str) -> Any | None:
        # Try exact match first, then regex
        for kwargs in [{"title": name}, {"title_re": re.escape(name)}]:
            try:
                wrapper = window.child_window(**kwargs)
                wrapper.wait("exists enabled", timeout=0.1)
                return wrapper
            except Exception:
                continue
        return None

    def _find_by_class(self, window: Any, class_name: str) -> Any | None:
        try:
            wrapper = window.child_window(class_name=class_name)
            wrapper.wait("exists enabled", timeout=0.1)
            return wrapper
        except Exception:
            return None

    def _find_by_control_type(self, window: Any, control_type: str) -> Any | None:
        if self._backend == "uia":
            try:
                wrapper = window.child_window(control_type=control_type)
                wrapper.wait("exists enabled", timeout=0.1)
                return wrapper
            except Exception:
                return None
        else:
            # win32 backend uses class_name to approximate control type
            return self._find_by_class(window, control_type)
