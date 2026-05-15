"""Recovery strategy implementations."""
from desktop_automation_platform.recovery.strategies.popup_dismissal import PopupDismissalStrategy
from desktop_automation_platform.recovery.strategies.stale_window import StaleWindowStrategy
from desktop_automation_platform.recovery.strategies.fuzzy_match import FuzzyMatchStrategy

__all__ = ["PopupDismissalStrategy", "StaleWindowStrategy", "FuzzyMatchStrategy"]
