"""
HealingTracker — process-level singleton that records every locator healing
event across an entire Robot Framework test run.

A "healing event" occurs when:
  - A primary locator strategy fails but a fallback succeeds (soft heal)
  - A recovery strategy (popup dismissal, stale window, fuzzy match) is applied
    and the action eventually succeeds (hard heal)

The tracker is thread-safe and reset at suite start by HealingListener.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar


@dataclass
class HealingEvent:
    """One locator healing occurrence."""
    locator_name: str
    test_name: str
    failed_strategy: str           # strategy that failed
    healed_by: str                 # strategy/recovery that succeeded
    heal_type: str                 # "fallback" | "fuzzy" | "popup_dismissed" | "stale_window"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    note: str = ""


class HealingTracker:
    """
    Thread-safe singleton.  Call HealingTracker.instance() to get it.
    """

    _instance: ClassVar["HealingTracker | None"] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self) -> None:
        self._events: list[HealingEvent] = []
        self._current_test: str = "<unknown>"
        self._event_lock = threading.Lock()

    @classmethod
    def instance(cls) -> "HealingTracker":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Test lifecycle hooks (called by HealingListener)
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all events — call at suite start."""
        with self._event_lock:
            self._events.clear()
            self._current_test = "<unknown>"

    def set_current_test(self, test_name: str) -> None:
        with self._event_lock:
            self._current_test = test_name

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_fallback(
        self,
        locator_name: str,
        failed_strategy: str,
        healed_by: str,
    ) -> None:
        """Record a soft heal — primary failed, fallback succeeded."""
        self._add(HealingEvent(
            locator_name=locator_name,
            test_name=self._current_test,
            failed_strategy=failed_strategy,
            healed_by=healed_by,
            heal_type="fallback",
        ))

    def record_recovery(
        self,
        locator_name: str,
        failed_strategy: str,
        heal_type: str,
        note: str = "",
    ) -> None:
        """Record a hard heal — recovery strategy applied."""
        self._add(HealingEvent(
            locator_name=locator_name,
            test_name=self._current_test,
            failed_strategy=failed_strategy,
            healed_by=heal_type,
            heal_type=heal_type,
            note=note,
        ))

    def _add(self, event: HealingEvent) -> None:
        with self._event_lock:
            self._events.append(event)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    @property
    def events(self) -> list[HealingEvent]:
        with self._event_lock:
            return list(self._events)

    def has_healed(self) -> bool:
        return bool(self._events)

    def summary(self) -> str:
        """One-paragraph text summary for Robot Framework log output."""
        events = self.events
        if not events:
            return "Self-Healing Report: No healing events recorded. All locators are healthy."

        by_locator: dict[str, list[HealingEvent]] = {}
        for e in events:
            by_locator.setdefault(e.locator_name, []).append(e)

        lines = [
            f"Self-Healing Report: {len(events)} healing event(s) across "
            f"{len(by_locator)} locator(s)\n"
        ]
        for locator, evts in sorted(by_locator.items()):
            heal_types = ", ".join(sorted({e.heal_type for e in evts}))
            tests = ", ".join(sorted({e.test_name for e in evts}))
            lines.append(
                f"  [{locator}]  healed {len(evts)}x  via={heal_types}  in: {tests}"
            )
            # Recommend updating the locator
            if any(e.heal_type == "fallback" for e in evts):
                winning = next(e.healed_by for e in evts if e.heal_type == "fallback")
                lines.append(
                    f"    → ACTION: promote '{winning}' to primary strategy in locators.yaml"
                )

        return "\n".join(lines)

    def yaml_report(self) -> str:
        """YAML-formatted report for writing to file."""
        import yaml
        events = self.events
        data = {
            "generated_at": datetime.utcnow().isoformat(),
            "total_events": len(events),
            "events": [
                {
                    "locator": e.locator_name,
                    "test": e.test_name,
                    "failed_strategy": e.failed_strategy,
                    "healed_by": e.healed_by,
                    "heal_type": e.heal_type,
                    "timestamp": e.timestamp.isoformat(),
                    "note": e.note,
                }
                for e in events
            ],
        }
        return yaml.dump(data, sort_keys=False, allow_unicode=True)
