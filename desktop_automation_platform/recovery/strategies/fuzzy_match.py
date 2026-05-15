"""
FuzzyMatchStrategy — last-resort element finder using approximate name matching.

When ALL locator strategies fail (primary + all fallbacks), this strategy
scans the entire visible UI tree and returns the element whose Name or
AutomationId is closest to the target value, provided the similarity
exceeds a minimum threshold.

Use case: an element's AutomationId changed slightly between releases
(e.g., "btnSubmit" → "btnSubmitClaim") but the element is still the same.

Similarity is computed with Python's built-in SequenceMatcher — no external
dependencies required.
"""

from __future__ import annotations

import difflib
from typing import Any

from desktop_automation_platform.core.models import ApplicationSession, UnifiedLocator
from desktop_automation_platform.utils.logger import get_logger

_log = get_logger(__name__)

# Minimum similarity ratio (0.0–1.0) to accept a fuzzy match
_MIN_RATIO = 0.72


class FuzzyMatchStrategy:
    """
    Scans the UIA tree for elements whose Name or AutomationId approximately
    matches any of the locator's strategy values.

    Works with FlaUI native context. No-op for other adapters.
    When a match is found, the matched element is stored on the session so
    the caller can use it directly.
    """

    heal_type = "fuzzy_match"

    def apply(
        self,
        locator: UnifiedLocator,
        session: ApplicationSession,
        native_context: dict[str, Any],
    ) -> bool:
        main_window = native_context.get("main_window")
        if main_window is None:
            return False

        # Collect all target values from the locator's strategies
        targets: list[str] = []
        for loc_def in locator.all_strategies():
            if loc_def.value:
                targets.append(str(loc_def.value))

        if not targets:
            return False

        try:
            match = self._find_fuzzy(main_window, targets)
            if match is not None:
                element, ratio, matched_target = match
                _log.info(
                    "fuzzy_match_found",
                    locator=locator.name,
                    target=matched_target,
                    ratio=round(ratio, 3),
                    element_name=str(getattr(element, "Name", "")),
                    element_id=str(getattr(element, "AutomationId", "")),
                )
                # Store the matched element so the adapter can use it directly
                native_context["fuzzy_matched_element"] = element
                return True
        except Exception as exc:
            _log.debug("fuzzy_match_error", error=str(exc))

        return False

    @staticmethod
    def _find_fuzzy(
        root: Any, targets: list[str]
    ) -> tuple[Any, float, str] | None:
        """
        BFS scan of the element tree; returns (element, ratio, matched_target)
        for the best match above the threshold, or None.
        """
        try:
            from FlaUI.Core.Conditions import TrueCondition  # type: ignore[import]
            from FlaUI.Core.Definitions import TreeScope  # type: ignore[import]
        except ImportError:
            return None

        best: tuple[Any, float, str] | None = None

        try:
            all_elements = root.FindAll(TreeScope.Descendants, TrueCondition.Default)
        except Exception:
            return None

        for element in all_elements:
            try:
                candidates: list[str] = []
                aid = str(element.AutomationId or "")
                name = str(element.Name or "")
                if aid:
                    candidates.append(aid)
                if name:
                    candidates.append(name)
                if not candidates:
                    continue

                for target in targets:
                    for candidate in candidates:
                        ratio = difflib.SequenceMatcher(
                            None, target.lower(), candidate.lower()
                        ).ratio()
                        if ratio >= _MIN_RATIO:
                            if best is None or ratio > best[1]:
                                best = (element, ratio, target)
            except Exception:
                continue

        return best
