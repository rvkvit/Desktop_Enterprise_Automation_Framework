"""
Scanner package — UI tree introspection and locator discovery.

Phase 4: walk a live application's UIA accessibility tree, score each element
for locator quality, and export a ready-to-use locators.yaml.

Public API
----------
    from desktop_automation_platform.scanner import scan_and_export

    scan_and_export(session, output_path, automation, resolver)
"""

from desktop_automation_platform.scanner.locator_generator import LocatorGenerator
from desktop_automation_platform.scanner.yaml_exporter import YamlExporter

__all__ = ["LocatorGenerator", "YamlExporter"]
