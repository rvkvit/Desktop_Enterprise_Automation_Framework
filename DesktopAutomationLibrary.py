# Top-level shim so Robot Framework can import the library as:
#   Library    DesktopAutomationLibrary
# The real implementation lives inside the platform package.
from desktop_automation_platform.robot_keywords.library import DesktopAutomationLibrary

__all__ = ["DesktopAutomationLibrary"]
