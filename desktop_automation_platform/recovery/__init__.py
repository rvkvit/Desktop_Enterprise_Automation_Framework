"""
Recovery package — self-healing locator engine and recovery strategies.

Public API
----------
    from desktop_automation_platform.recovery import RecoveryManager, HealingTracker
    from desktop_automation_platform.recovery.strategies import (
        PopupDismissalStrategy,
        StaleWindowStrategy,
        FuzzyMatchStrategy,
    )

Default FlaUI recovery manager
-------------------------------
    manager = build_default_flaui_recovery_manager()

Pre-configures a RecoveryManager with all three strategies in priority order:
    1. PopupDismissalStrategy  — fastest: dismiss blocking dialogs
    2. StaleWindowStrategy     — re-attach on stale HWND
    3. FuzzyMatchStrategy      — last resort: approximate name matching
"""

from desktop_automation_platform.recovery.healing_tracker import HealingEvent, HealingTracker
from desktop_automation_platform.recovery.recovery_manager import RecoveryManager
from desktop_automation_platform.recovery.robot_listener import HealingListener

__all__ = [
    "HealingTracker",
    "HealingEvent",
    "RecoveryManager",
    "HealingListener",
    "build_default_flaui_recovery_manager",
]


def build_default_flaui_recovery_manager() -> RecoveryManager:
    """Return a RecoveryManager pre-loaded with the standard FlaUI strategy set."""
    from desktop_automation_platform.recovery.strategies import (
        FuzzyMatchStrategy,
        PopupDismissalStrategy,
        StaleWindowStrategy,
    )

    manager = RecoveryManager()
    manager.register(PopupDismissalStrategy())
    manager.register(StaleWindowStrategy())
    manager.register(FuzzyMatchStrategy())
    return manager
