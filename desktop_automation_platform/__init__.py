"""
Desktop Automation Platform
===========================
Enterprise-grade, adapter-driven desktop automation framework for QA teams.
Supports WPF, WinForms, WinUI3, MAUI, Win32, Java Swing, Qt, Electron,
Citrix/RDP, and Windows Packaged applications via a unified Robot Framework
keyword layer.

Quickstart
----------
    from desktop_automation_platform.core.container import PlatformContainer
    from desktop_automation_platform.config.yaml_loader import YamlConfigLoader

    config = YamlConfigLoader().load("config.yaml")
    container = PlatformContainer(config=config)
    container.wire(modules=[__name__])
"""

__version__ = "1.0.0"
__author__ = "QA Platform Team"
