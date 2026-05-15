"""
WinAppDriverElementResolver — finds elements via Appium/WebDriver By locators.

Strategy mapping
----------------
  automation_id → By.ACCESSIBILITY_ID
  name          → By.NAME
  class_name    → By.CLASS_NAME
  xpath         → By.XPATH
  control_type  → By.XPATH (//ControlType[@...])
"""

from __future__ import annotations

import time
from typing import Any

from desktop_automation_platform.core.models import LocatorDefinition, LocatorStrategy
from desktop_automation_platform.utils.logger import get_logger

_log = get_logger(__name__)


class WinAppDriverElementResolver:

    def find_element(
        self,
        driver: Any,
        loc_def: LocatorDefinition,
        timeout_seconds: float = 10.0,
    ) -> Any:
        by, value = self._map(loc_def)
        from selenium.webdriver.support.ui import WebDriverWait  # type: ignore[import]
        from selenium.webdriver.support import expected_conditions as EC  # type: ignore[import]
        from selenium.webdriver.common.by import By  # type: ignore[import]
        try:
            return WebDriverWait(driver, timeout_seconds).until(
                EC.presence_of_element_located((by, value))
            )
        except Exception as exc:
            raise RuntimeError(
                f"Element not found: {loc_def.strategy.value}={loc_def.value!r} "
                f"within {timeout_seconds}s — {exc}"
            ) from exc

    def element_exists(
        self,
        driver: Any,
        loc_def: LocatorDefinition,
        timeout_seconds: float = 3.0,
    ) -> bool:
        try:
            self.find_element(driver, loc_def, timeout_seconds)
            return True
        except Exception:
            return False

    @staticmethod
    def _map(loc_def: LocatorDefinition) -> tuple[str, str]:
        from selenium.webdriver.common.by import By  # type: ignore[import]
        s = loc_def.strategy
        v = str(loc_def.value)
        if s == LocatorStrategy.AUTOMATION_ID:
            return By.ACCESSIBILITY_ID, v
        if s == LocatorStrategy.NAME:
            return By.NAME, v
        if s == LocatorStrategy.CLASS_NAME:
            return By.CLASS_NAME, v
        if s == LocatorStrategy.XPATH:
            return By.XPATH, v
        if s == LocatorStrategy.CONTROL_TYPE:
            return By.XPATH, f"//{v}"
        # Fallback
        return By.NAME, v
