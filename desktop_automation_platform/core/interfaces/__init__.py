"""
Core interface contracts for the Desktop Automation Platform.

Every injectable service in the platform implements one of these ABCs.
The dependency injection container binds concrete implementations to
these interfaces, keeping all framework code adapter-agnostic.
"""

from desktop_automation_platform.core.interfaces.application_adapter import IApplicationAdapter
from desktop_automation_platform.core.interfaces.application_detector import IApplicationDetector
from desktop_automation_platform.core.interfaces.config_manager import IConfigManager
from desktop_automation_platform.core.interfaces.execution_engine import IExecutionEngine
from desktop_automation_platform.core.interfaces.locator_scanner import ILocatorScanner
from desktop_automation_platform.core.interfaces.locator_translator import ILocatorTranslator
from desktop_automation_platform.core.interfaces.recovery_engine import IRecoveryEngine
from desktop_automation_platform.core.interfaces.reporter import IReporter
from desktop_automation_platform.core.interfaces.screenshot_manager import IScreenshotManager

__all__ = [
    "IApplicationAdapter",
    "IApplicationDetector",
    "IConfigManager",
    "IExecutionEngine",
    "ILocatorScanner",
    "ILocatorTranslator",
    "IRecoveryEngine",
    "IReporter",
    "IScreenshotManager",
]
