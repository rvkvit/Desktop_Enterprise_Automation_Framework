"""
FlaUILocatorScanner — ILocatorScanner implementation using FlaUI UIA tree walking.

Walks the live UI Automation accessibility tree of a running application and
produces:
1. ``ElementInfo`` objects consumed by the locator engine
2. YAML locator repositories (for test authors)
3. Robot Framework ``.resource`` files (variable declarations)

Tree walking strategy
---------------------
BFS from the application main window, bounded by ``max_depth``.
Each element's automation properties are extracted via the UIA element interface.
Elements without a usable identifier (no AutomationId, Name, or ClassName) are
included in the tree snapshot but excluded from locator repo generation.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from desktop_automation_platform.adapters.flaui.element_resolver import FlaUIElementResolver
from desktop_automation_platform.core.interfaces.locator_scanner import ILocatorScanner
from desktop_automation_platform.core.models import (
    ApplicationSession,
    ElementInfo,
    UnifiedLocator,
)
from desktop_automation_platform.utils.logger import get_logger

if TYPE_CHECKING:
    pass

_log = get_logger(__name__)

_IDENTIFIER_SANITIZE = re.compile(r"[^A-Za-z0-9_]")


def _make_locator_name(element: ElementInfo, existing: set[str]) -> str:
    """
    Generate a unique UPPER_SNAKE_CASE locator name from element properties.
    Priority: AutomationId → Name → ClassName + ControlType
    """
    parts: list[str] = []
    if element.automation_id:
        parts.append(element.automation_id)
    elif element.name:
        parts.append(element.name)
    elif element.class_name:
        parts.append(element.class_name)
    if element.control_type:
        parts.append(element.control_type)

    raw = "_".join(parts) if parts else "ELEMENT"
    clean = _IDENTIFIER_SANITIZE.sub("_", raw).upper().strip("_")
    clean = re.sub(r"_+", "_", clean)

    # Ensure uniqueness by appending a counter
    candidate = clean
    counter = 2
    while candidate in existing:
        candidate = f"{clean}_{counter}"
        counter += 1
    return candidate


class FlaUILocatorScanner(ILocatorScanner):
    """
    Scans the live UIA tree via FlaUI and produces locator artefacts.
    """

    def __init__(self, automation: Any, resolver: FlaUIElementResolver) -> None:
        self._automation = automation
        self._resolver = resolver

    # ------------------------------------------------------------------
    # ILocatorScanner
    # ------------------------------------------------------------------

    def scan_application(
        self,
        session: ApplicationSession,
        max_depth: int = 10,
    ) -> list[ElementInfo]:
        """Walk the full UI tree starting from the application main window."""
        native = self._get_native(session)
        main_window = native.get("main_window")
        if main_window is None:
            raise RuntimeError(
                f"Session {session.session_id} has no main_window in native_session. "
                "Call launch_application or attach_application first."
            )
        _log.info(
            "scan_application_started",
            session_id=session.session_id,
            max_depth=max_depth,
        )
        elements = self._walk_tree(main_window, depth=0, max_depth=max_depth, parent_id=None)
        _log.info("scan_application_complete", element_count=len(elements))
        return elements

    def scan_element(
        self,
        session: ApplicationSession,
        locator: UnifiedLocator,
        max_depth: int = 5,
    ) -> list[ElementInfo]:
        """Walk the subtree rooted at the element identified by ``locator``."""
        native = self._get_native(session)
        main_window = native.get("main_window")
        resolver = self._resolver

        # Find the root element for the subtree scan
        for loc_def in locator.all_strategies():
            try:
                timeout = loc_def.timeout or 10.0
                element = resolver.find_element(main_window, loc_def, timeout_seconds=timeout)
                _log.info(
                    "scan_element_started",
                    locator=locator.name,
                    strategy=loc_def.strategy.value,
                )
                return self._walk_tree(element, depth=0, max_depth=max_depth, parent_id=None)
            except Exception:
                continue

        raise RuntimeError(f"Could not find element for locator '{locator.name}' to scan.")

    def export_yaml(
        self,
        elements: list[ElementInfo],
        output_path: str,
        overwrite: bool = False,
    ) -> str:
        """Generate a YAML locator repository from the scanned elements."""
        path = Path(output_path)
        if path.exists() and not overwrite:
            raise FileExistsError(f"Output path already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)

        repo: dict[str, Any] = {}
        existing_names: set[str] = set()

        for elem in elements:
            if not self._is_identifiable(elem):
                continue
            name = _make_locator_name(elem, existing_names)
            existing_names.add(name)
            entry = self._element_to_yaml_entry(elem)
            repo[name] = entry

        path.write_text(
            yaml.dump(repo, sort_keys=True, allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )
        _log.info("yaml_repo_exported", path=str(path), count=len(repo))
        return str(path)

    def export_robot_resource(
        self,
        elements: list[ElementInfo],
        output_path: str,
        overwrite: bool = False,
    ) -> str:
        """Generate a Robot Framework .resource file with variable definitions."""
        path = Path(output_path)
        if path.exists() and not overwrite:
            raise FileExistsError(f"Output path already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)

        lines: list[str] = [
            "*** Settings ***",
            f"Documentation    Auto-generated locator resource. DO NOT EDIT MANUALLY.",
            "",
            "*** Variables ***",
        ]

        existing_names: set[str] = set()
        for elem in elements:
            if not self._is_identifiable(elem):
                continue
            name = _make_locator_name(elem, existing_names)
            existing_names.add(name)
            primary = self._primary_strategy(elem)
            comment = f"    # {elem.control_type or ''} {elem.name or ''}".rstrip()
            lines.append(f"${{{name}}}    {primary}{comment}")

        lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        _log.info("robot_resource_exported", path=str(path), count=len(existing_names))
        return str(path)

    # ------------------------------------------------------------------
    # Tree walking
    # ------------------------------------------------------------------

    def _walk_tree(
        self,
        element: Any,
        depth: int,
        max_depth: int,
        parent_id: str | None,
    ) -> list[ElementInfo]:
        """Recursive BFS / DFS element tree walker."""
        if depth > max_depth:
            return []

        info = self._extract_element_info(element, parent_id)
        results: list[ElementInfo] = [info]

        if depth < max_depth:
            try:
                from FlaUI.Core.Definitions import TreeScope  # type: ignore[import]

                from FlaUI.Core.Conditions import TrueCondition  # type: ignore[import]

                children = element.FindAll(TreeScope.Children, TrueCondition.Default)
                for child in children:
                    try:
                        child_results = self._walk_tree(
                            child,
                            depth=depth + 1,
                            max_depth=max_depth,
                            parent_id=info.automation_id,
                        )
                        results.extend(child_results)
                        # Add immediate children to info.children
                        if child_results:
                            info.children.append(child_results[0])
                    except Exception:
                        continue
            except Exception as exc:
                _log.debug("tree_walk_children_failed", depth=depth, error=str(exc))

        return results

    def _extract_element_info(self, element: Any, parent_id: str | None) -> ElementInfo:
        """Extract all available UIA properties from an element."""
        info = ElementInfo(parent_automation_id=parent_id)
        try:
            info.automation_id = str(element.AutomationId or "") or None
        except Exception:
            pass
        try:
            info.name = str(element.Name or "") or None
        except Exception:
            pass
        try:
            info.class_name = str(element.ClassName or "") or None
        except Exception:
            pass
        try:
            info.control_type = str(element.ControlType).split(".")[-1] or None
        except Exception:
            pass
        try:
            info.is_enabled = bool(element.IsEnabled)
        except Exception:
            info.is_enabled = True
        try:
            info.is_visible = not bool(element.IsOffscreen)
        except Exception:
            info.is_visible = True
        try:
            rect = element.BoundingRectangle
            info.bounding_rect = {
                "x": int(rect.X),
                "y": int(rect.Y),
                "width": int(rect.Width),
                "height": int(rect.Height),
            }
        except Exception:
            pass
        try:
            patterns = []
            pattern_names = [
                "Invoke", "Value", "SelectionItem", "Selection", "ExpandCollapse",
                "Window", "Text", "Toggle", "Scroll", "Grid", "Table",
            ]
            for p in pattern_names:
                try:
                    pat = getattr(element.Patterns, p, None)
                    if pat and pat.IsSupported:
                        patterns.append(p)
                except Exception:
                    pass
            info.supported_patterns = patterns
        except Exception:
            pass
        try:
            info.runtime_id = str(element.RuntimeId)
        except Exception:
            pass
        return info

    # ------------------------------------------------------------------
    # YAML helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_identifiable(elem: ElementInfo) -> bool:
        """Return True if the element has at least one usable identifier."""
        return bool(elem.automation_id or elem.name or elem.class_name)

    @staticmethod
    def _primary_strategy(elem: ElementInfo) -> str:
        """Return the best primary locator value string for Robot Framework."""
        if elem.automation_id:
            return f"automation_id:{elem.automation_id}"
        if elem.name:
            return f"name:{elem.name}"
        if elem.class_name:
            return f"class_name:{elem.class_name}"
        return "unknown"

    def _element_to_yaml_entry(self, elem: ElementInfo) -> dict[str, Any]:
        """Convert an ElementInfo to a locator repository YAML entry."""
        entry: dict[str, Any] = {}
        primary: dict[str, Any] = {}
        fallbacks: list[dict[str, Any]] = []

        # Choose primary strategy (automation_id first, then name, then class)
        if elem.automation_id:
            primary = {"strategy": "automation_id", "value": elem.automation_id}
            if elem.name:
                fallbacks.append({"strategy": "name", "value": elem.name})
            if elem.class_name:
                fallbacks.append({"strategy": "class_name", "value": elem.class_name})
        elif elem.name:
            primary = {"strategy": "name", "value": elem.name}
            if elem.class_name:
                fallbacks.append({"strategy": "class_name", "value": elem.class_name})
        elif elem.class_name:
            primary = {"strategy": "class_name", "value": elem.class_name}

        # Add control_type as a narrowing fallback
        if elem.control_type and elem.name:
            fallbacks.append({"strategy": "control_type", "value": elem.control_type.lower()})

        entry["primary"] = primary
        if fallbacks:
            entry["fallbacks"] = fallbacks

        # Metadata
        meta: dict[str, Any] = {}
        if elem.control_type:
            meta["control_type"] = elem.control_type
        if elem.bounding_rect:
            meta["bounding_rect"] = elem.bounding_rect
        if elem.is_enabled is False:
            meta["is_enabled"] = False
        if elem.supported_patterns:
            meta["supported_patterns"] = elem.supported_patterns
        if meta:
            entry["metadata"] = meta

        return entry

    # ------------------------------------------------------------------
    # Session helper
    # ------------------------------------------------------------------

    @staticmethod
    def _get_native(session: ApplicationSession) -> dict[str, Any]:
        if not isinstance(session.native_session, dict):
            raise RuntimeError(
                f"FlaUI native session expected dict, got {type(session.native_session)}"
            )
        return session.native_session
