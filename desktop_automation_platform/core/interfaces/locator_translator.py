"""
ILocatorTranslator — framework-neutral → adapter-native locator translation.

Each adapter ships its own LocatorTranslator that maps ``UnifiedLocator``
strategies to the native selector objects the adapter's underlying engine
understands (e.g. FlaUI ``ByAutomationId``, Playwright CSS, XPath, etc.).

The translation layer is intentionally separated from the adapter so it can
be unit-tested without spinning up a live UI automation session.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from desktop_automation_platform.core.models import AdapterType, LocatorDefinition


class ILocatorTranslator(ABC):
    """
    Translates a ``LocatorDefinition`` into the native locator object
    expected by a specific automation engine.

    Concrete implementations live in ``adapters/<adapter_name>/translator.py``.
    """

    @property
    @abstractmethod
    def adapter_type(self) -> AdapterType:
        """Adapter this translator serves."""
        ...

    @abstractmethod
    def translate(self, locator: LocatorDefinition) -> Any:
        """
        Convert a single ``LocatorDefinition`` to the adapter-native selector.

        Returns a native selector object (type varies per adapter).
        Raises ``LocatorResolutionException`` if the strategy is not supported.
        """
        ...

    @abstractmethod
    def supports_strategy(self, strategy: str) -> bool:
        """
        Return True if this translator can handle the given ``LocatorStrategy``
        value without raising.  Used by the locator engine to prune the
        fallback chain before attempting resolution.
        """
        ...

    @abstractmethod
    def supported_strategies(self) -> list[str]:
        """Return all strategy names this translator handles."""
        ...
