"""
FlaUI ControlType string → enum mapping.

Robot Framework tests and YAML locator files use human-readable control type
names (e.g. "Button", "Edit", "ComboBox").  This module translates those
strings to the FlaUI ``ControlType`` .NET enum values used in search conditions.

Values are loaded lazily to avoid import-time CLR dependency.

Complete mapping covers all 32 standard UIA ControlType values, plus
common aliases used by testers who come from a Selenium background.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# String → ControlType mapping (lazy-loaded)
# ---------------------------------------------------------------------------

# String name → FlaUI ControlType enum attribute name (exact .NET spelling)
_CONTROL_TYPE_NAMES: dict[str, str] = {
    # Standard UIA names
    "appbar": "AppBar",
    "button": "Button",
    "calendar": "Calendar",
    "checkbox": "CheckBox",
    "combobox": "ComboBox",
    "custom": "Custom",
    "datagrid": "DataGrid",
    "dataitem": "DataItem",
    "document": "Document",
    "edit": "Edit",
    "group": "Group",
    "header": "Header",
    "headeritem": "HeaderItem",
    "hyperlink": "Hyperlink",
    "image": "Image",
    "list": "List",
    "listitem": "ListItem",
    "menu": "Menu",
    "menubar": "MenuBar",
    "menuitem": "MenuItem",
    "pane": "Pane",
    "progressbar": "ProgressBar",
    "radiobutton": "RadioButton",
    "scrollbar": "ScrollBar",
    "separator": "Separator",
    "slider": "Slider",
    "spinner": "Spinner",
    "splitbutton": "SplitButton",
    "statusbar": "StatusBar",
    "tab": "Tab",
    "tabitem": "TabItem",
    "table": "Table",
    "text": "Text",
    "thumb": "Thumb",
    "titlebar": "TitleBar",
    "toolbar": "ToolBar",
    "tooltip": "ToolTip",
    "tree": "Tree",
    "treeitem": "TreeItem",
    "window": "Window",
    # Common aliases / Selenium-like names
    "textbox": "Edit",
    "input": "Edit",
    "label": "Text",
    "statictext": "Text",
    "link": "Hyperlink",
    "anchor": "Hyperlink",
    "listbox": "List",
    "dropdown": "ComboBox",
    "select": "ComboBox",
    "check": "CheckBox",
    "radio": "RadioButton",
    "grid": "DataGrid",
    "table_row": "DataItem",
    "tab_panel": "TabItem",
    "frame": "Window",
    "dialog": "Window",
}


def resolve_control_type(name: str) -> Any:
    """
    Resolve a control type name string to the FlaUI ``ControlType`` enum value.

    Case-insensitive. Raises ``ValueError`` for unknown names.

    Usage::

        ct = resolve_control_type("Button")
        condition = automation.ConditionFactory.ByControlType(ct)
    """
    normalised = name.strip().lower().replace(" ", "").replace("_", "")
    attr_name = _CONTROL_TYPE_NAMES.get(normalised)
    if attr_name is None:
        known = sorted(set(_CONTROL_TYPE_NAMES.values()))
        raise ValueError(
            f"Unknown control type: {name!r}. "
            f"Known types: {known}"
        )
    try:
        from FlaUI.Core.Definitions import ControlType  # type: ignore[import]

        return getattr(ControlType, attr_name)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load FlaUI ControlType.{attr_name}: {exc}"
        ) from exc


def list_supported_control_types() -> list[str]:
    """Return all supported control type string values."""
    return sorted(_CONTROL_TYPE_NAMES.keys())
