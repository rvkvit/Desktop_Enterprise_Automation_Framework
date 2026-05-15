"""
FlaUILocatorTranslator — ILocatorTranslator implementation for the FlaUI adapter.

Maps every supported ``LocatorStrategy`` to the native FlaUI ``ConditionBase``
object used in ``AutomationElement.FindFirst / FindAll``.

Strategies supported natively by FlaUI UIA
-------------------------------------------
✓ automation_id   → ConditionFactory.ByAutomationId(value)
✓ name            → ConditionFactory.ByName(value)
✓ class_name      → ConditionFactory.ByClassName(value)
✓ control_type    → ConditionFactory.ByControlType(ControlType.*)
✓ text            → ConditionFactory.ByName(value)   (UI text = Name in UIA)
✓ partial_text    → PropertyCondition(Name, value, IgnoreCase) — substring
✓ runtime_id      → ConditionFactory.ByRuntimeId(int[])

Strategies NOT supported natively
-----------------------------------
✗ xpath           → UIA has no XPath; raises LocatorResolutionException
                    (locator repo should always have a UIA fallback)
✗ image           → pixel-based; handled by SikuliImageAdapter fallback
✗ css_selector    → web-only; handled by ElectronPlaywrightAdapter
✗ tag_name        → web-only; handled by ElectronPlaywrightAdapter
✗ accessibility_id→ same as automation_id in Windows UIA
✗ coordinates     → not a find-element strategy; handled at click level

The translator raises ``LocatorResolutionException`` for unsupported strategies
so the locator engine can skip to the next fallback in the chain.
"""

from __future__ import annotations

from typing import Any

from desktop_automation_platform.adapters.flaui.control_type_map import resolve_control_type
from desktop_automation_platform.core.exceptions import LocatorResolutionException
from desktop_automation_platform.core.interfaces.locator_translator import ILocatorTranslator
from desktop_automation_platform.core.models import AdapterType, LocatorDefinition, LocatorStrategy
from desktop_automation_platform.utils.logger import get_logger

_log = get_logger(__name__)

# Strategies this translator can handle
_SUPPORTED_STRATEGIES: frozenset[LocatorStrategy] = frozenset(
    [
        LocatorStrategy.AUTOMATION_ID,
        LocatorStrategy.NAME,
        LocatorStrategy.CLASS_NAME,
        LocatorStrategy.CONTROL_TYPE,
        LocatorStrategy.TEXT,
        LocatorStrategy.PARTIAL_TEXT,
        LocatorStrategy.RUNTIME_ID,
        LocatorStrategy.ACCESSIBILITY_ID,  # treated as automation_id on Windows
    ]
)

_UNSUPPORTED_STRATEGIES: frozenset[LocatorStrategy] = frozenset(
    [
        LocatorStrategy.XPATH,
        LocatorStrategy.IMAGE,
        LocatorStrategy.CSS_SELECTOR,
        LocatorStrategy.TAG_NAME,
        LocatorStrategy.COORDINATES,
    ]
)


class FlaUILocatorTranslator(ILocatorTranslator):
    """
    Translates ``LocatorDefinition`` instances to FlaUI ``ConditionBase`` objects.

    One instance per automation session is sufficient; the translator is stateless.
    """

    def __init__(self, automation: Any) -> None:
        """
        Parameters
        ----------
        automation:
            UIA3Automation or UIA2Automation instance.
        """
        self._automation = automation
        self._condition_factory = automation.ConditionFactory

    # ------------------------------------------------------------------
    # ILocatorTranslator
    # ------------------------------------------------------------------

    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.FLAUI

    def translate(self, locator: LocatorDefinition) -> Any:
        """
        Translate ``locator`` to a FlaUI ``ConditionBase``.

        Returns the condition object (passed directly to ``FindFirst``).
        Raises ``LocatorResolutionException`` for unsupported strategies.
        """
        strategy = locator.strategy
        value = locator.value
        cf = self._condition_factory

        _log.debug(
            "translating_locator",
            strategy=strategy.value,
            value=value,
            adapter="flaui",
        )

        if strategy in _UNSUPPORTED_STRATEGIES:
            raise LocatorResolutionException(
                locator_name=value,
                strategy=strategy.value,
                adapter_type="flaui",
            )

        try:
            if strategy in (LocatorStrategy.AUTOMATION_ID, LocatorStrategy.ACCESSIBILITY_ID):
                return cf.ByAutomationId(value)

            elif strategy == LocatorStrategy.NAME:
                return cf.ByName(value)

            elif strategy == LocatorStrategy.CLASS_NAME:
                return cf.ByClassName(value)

            elif strategy == LocatorStrategy.CONTROL_TYPE:
                return cf.ByControlType(resolve_control_type(value))

            elif strategy == LocatorStrategy.TEXT:
                # In Windows UIA, the visible text of an element is its Name property
                return cf.ByName(value)

            elif strategy == LocatorStrategy.PARTIAL_TEXT:
                return self._partial_name_condition(value)

            elif strategy == LocatorStrategy.RUNTIME_ID:
                return cf.ByRuntimeId(self._parse_runtime_id(value))

            else:
                raise LocatorResolutionException(
                    locator_name=value,
                    strategy=strategy.value,
                    adapter_type="flaui",
                )

        except LocatorResolutionException:
            raise
        except Exception as exc:
            raise LocatorResolutionException(
                locator_name=value,
                strategy=strategy.value,
                adapter_type="flaui",
            ) from exc

    def supports_strategy(self, strategy: str) -> bool:
        try:
            return LocatorStrategy(strategy) in _SUPPORTED_STRATEGIES
        except ValueError:
            return False

    def supported_strategies(self) -> list[str]:
        return sorted(s.value for s in _SUPPORTED_STRATEGIES)

    # ------------------------------------------------------------------
    # Compound conditions
    # ------------------------------------------------------------------

    def translate_compound(
        self,
        locator: LocatorDefinition,
        additional_control_type: str | None = None,
    ) -> Any:
        """
        Build a compound AND condition: primary strategy + optional ControlType filter.

        Useful for disambiguation when ``name`` matches multiple element types::

            translator.translate_compound(
                LocatorDefinition(LocatorStrategy.NAME, "Login"),
                additional_control_type="Button",
            )
        """
        base_condition = self.translate(locator)
        if additional_control_type is None:
            return base_condition

        ct_condition = self._condition_factory.ByControlType(
            resolve_control_type(additional_control_type)
        )
        try:
            return base_condition.And(ct_condition)
        except Exception:
            # Fallback: return base condition if AND composition fails
            return base_condition

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _partial_name_condition(self, partial_name: str) -> Any:
        """Build a UIA PropertyCondition for Name contains partial_name."""
        try:
            from FlaUI.Core.Conditions import PropertyCondition  # type: ignore[import]
            from FlaUI.Core.Definitions import PropertyConditionFlags  # type: ignore[import]

            prop_id = self._automation.PropertyLibrary.Element.Name
            return PropertyCondition(
                prop_id,
                partial_name,
                PropertyConditionFlags.IgnoreCase,
            )
        except Exception:
            _log.warning(
                "partial_name_condition_degraded",
                value=partial_name,
                reason="PropertyConditionFlags unavailable; using exact ByName",
            )
            return self._condition_factory.ByName(partial_name)

    @staticmethod
    def _parse_runtime_id(value: str) -> Any:
        """Parse comma/space-separated integers into a .NET int[] array."""
        try:
            parts = [int(x.strip()) for x in value.replace(",", " ").split()]
            import System  # type: ignore[import]

            return System.Array[System.Int32](parts)
        except Exception as exc:
            raise ValueError(
                f"Invalid runtime_id value {value!r}. "
                f"Expected comma-separated integers, e.g. '42, 0, 7'. Error: {exc}"
            ) from exc
