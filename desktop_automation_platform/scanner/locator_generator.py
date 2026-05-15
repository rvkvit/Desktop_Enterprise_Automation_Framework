"""
LocatorGenerator — scores ElementInfo trees and selects the best locator
strategy for each interactable element.

Strategy scoring (highest wins)
--------------------------------
  automation_id  → 100  stable developer-assigned identifier
  name           →  70  accessible name (label / button caption)
  class_name     →  40  Win32 class name — stable but not unique
  control_type   →  20  used as a tiebreaker / fallback only
  xpath          →   5  last resort, fragile

Filtering rules
---------------
- Offscreen or zero-size elements are skipped (not interactable).
- Container types (Pane, Group, Window, Custom without ID/name) are included
  only if they have a usable automation_id or name — they are rarely targeted
  in tests but are useful as scope anchors.
- Elements with no identifier at all are dropped entirely.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from desktop_automation_platform.core.models import ElementInfo
from desktop_automation_platform.utils.logger import get_logger

_log = get_logger(__name__)

# Control types that are generally not direct interaction targets
_CONTAINER_TYPES = frozenset({
    "Pane", "Group", "Window", "Tab", "TabItem",
    "ToolBar", "MenuBar", "StatusBar", "ScrollBar",
})

# Control types that are always worth including regardless of other filters
_INTERACTION_TYPES = frozenset({
    "Button", "CheckBox", "RadioButton", "ComboBox", "Edit",
    "Document", "ListItem", "MenuItem", "Hyperlink", "Slider",
    "Spinner", "TreeItem", "DataItem", "HeaderItem",
    "SplitButton", "ToggleButton", "Calendar", "DataGrid", "List", "Tree",
})

_SANITIZE = re.compile(r"[^A-Za-z0-9_]")


@dataclass
class ScoredElement:
    """An ElementInfo enriched with a locator key name and quality score."""
    element: ElementInfo
    key: str                          # UPPER_SNAKE_CASE locator key
    primary_strategy: str             # automation_id | name | class_name | control_type
    primary_value: str
    fallbacks: list[dict[str, str]] = field(default_factory=list)
    score: int = 0
    skip_reason: str | None = None    # set when element is filtered out


class LocatorGenerator:
    """
    Converts a flat list of ElementInfo objects (from the FlaUI scanner) into
    scored, named ScoredElement records ready for YAML export.
    """

    def __init__(
        self,
        include_containers: bool = False,
        include_invisible: bool = False,
        min_score: int = 20,
    ) -> None:
        """
        Parameters
        ----------
        include_containers:
            Include Pane/Group/Window elements even without unique identifiers.
        include_invisible:
            Include offscreen or zero-size elements.
        min_score:
            Minimum quality score for an element to be included in output.
            Default 20 — drops elements identified only by control_type.
        """
        self._include_containers = include_containers
        self._include_invisible = include_invisible
        self._min_score = min_score

    def generate(self, elements: list[ElementInfo]) -> list[ScoredElement]:
        """
        Score and name every element. Returns only elements that pass
        the quality threshold, in tree order.
        """
        used_keys: set[str] = set()
        results: list[ScoredElement] = []

        for elem in elements:
            scored = self._score(elem, used_keys)
            if scored.skip_reason:
                _log.debug(
                    "element_skipped",
                    reason=scored.skip_reason,
                    name=elem.name,
                    automation_id=elem.automation_id,
                    control_type=elem.control_type,
                )
                continue
            used_keys.add(scored.key)
            results.append(scored)

        _log.info(
            "locator_generation_complete",
            total_input=len(elements),
            total_output=len(results),
        )
        return results

    # ------------------------------------------------------------------
    # Internal scoring
    # ------------------------------------------------------------------

    def _score(self, elem: ElementInfo, used_keys: set[str]) -> ScoredElement:
        scored = ScoredElement(
            element=elem,
            key="",
            primary_strategy="",
            primary_value="",
        )

        # 1. Visibility filter
        if not self._include_invisible:
            if not elem.is_visible:
                scored.skip_reason = "offscreen"
                return scored
            if elem.bounding_rect and (
                elem.bounding_rect.get("width", 1) == 0
                or elem.bounding_rect.get("height", 1) == 0
            ):
                scored.skip_reason = "zero_size"
                return scored

        # 2. Identifiability filter
        if not (elem.automation_id or elem.name or elem.class_name):
            scored.skip_reason = "no_identifier"
            return scored

        # 3. Container filter
        ct = elem.control_type or ""
        is_container = ct in _CONTAINER_TYPES
        if is_container and not self._include_containers:
            if not (elem.automation_id or elem.name):
                scored.skip_reason = "unnamed_container"
                return scored

        # 4. Choose primary strategy and score
        fallbacks: list[dict[str, str]] = []

        if elem.automation_id:
            scored.primary_strategy = "automation_id"
            scored.primary_value = elem.automation_id
            scored.score = 100
            if elem.name:
                fallbacks.append({"strategy": "name", "value": elem.name})
            if elem.class_name:
                fallbacks.append({"strategy": "class_name", "value": elem.class_name})
            if ct:
                fallbacks.append({"strategy": "control_type", "value": ct})

        elif elem.name:
            scored.primary_strategy = "name"
            scored.primary_value = elem.name
            scored.score = 70
            if elem.class_name:
                fallbacks.append({"strategy": "class_name", "value": elem.class_name})
            if ct:
                fallbacks.append({"strategy": "control_type", "value": ct})

        elif elem.class_name:
            scored.primary_strategy = "class_name"
            scored.primary_value = elem.class_name
            scored.score = 40
            if ct:
                fallbacks.append({"strategy": "control_type", "value": ct})

        elif ct:
            scored.primary_strategy = "control_type"
            scored.primary_value = ct
            scored.score = 20

        scored.fallbacks = fallbacks

        # 5. Minimum score gate
        if scored.score < self._min_score:
            scored.skip_reason = f"score_below_threshold ({scored.score} < {self._min_score})"
            return scored

        # 6. Generate key name
        scored.key = self._make_key(elem, used_keys)
        return scored

    @staticmethod
    def _make_key(elem: ElementInfo, used_keys: set[str]) -> str:
        """Generate a unique UPPER_SNAKE_CASE key from element properties."""
        parts: list[str] = []

        source = elem.automation_id or elem.name or elem.class_name or ""
        if source:
            parts.append(source)

        ct = elem.control_type or ""
        if ct and ct not in _CONTAINER_TYPES:
            parts.append(ct)

        raw = "_".join(parts) if parts else "ELEMENT"
        clean = _SANITIZE.sub("_", raw).upper().strip("_")
        clean = re.sub(r"_+", "_", clean)
        if not clean:
            clean = "ELEMENT"

        candidate = clean
        counter = 2
        while candidate in used_keys:
            candidate = f"{clean}_{counter}"
            counter += 1
        return candidate
