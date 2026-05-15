"""
AdapterRegistry — central catalogue of available desktop adapter implementations.

The registry maps AdapterType → adapter factory / class. Adapters register
themselves at import time using ``registry.register()``.  The AdapterManager
queries the registry to resolve the correct adapter for a given application
technology without knowing concrete adapter classes.

Design decisions
----------------
* Factories (callables) are stored rather than instances so that adapters
  are only instantiated when actually needed.
* Availability is checked at registration time; unavailable adapters are
  tracked separately so the manager can surface helpful diagnostics.
* The registry is a singleton within the DI container — all modules share
  the same instance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from desktop_automation_platform.core.models import AdapterType, ApplicationTechnology
from desktop_automation_platform.utils.logger import get_logger

if TYPE_CHECKING:
    from desktop_automation_platform.core.interfaces.application_adapter import (
        IApplicationAdapter,
    )

_log = get_logger(__name__)

# Type alias for adapter factory callable
AdapterFactory = Callable[[], "IApplicationAdapter"]


class AdapterRegistration:
    """Metadata record stored for each registered adapter."""

    __slots__ = ("adapter_type", "factory", "supported_technologies", "available", "unavailable_reason")

    def __init__(
        self,
        adapter_type: AdapterType,
        factory: AdapterFactory,
        supported_technologies: list[ApplicationTechnology],
        available: bool,
        unavailable_reason: str | None = None,
    ) -> None:
        self.adapter_type = adapter_type
        self.factory = factory
        self.supported_technologies = supported_technologies
        self.available = available
        self.unavailable_reason = unavailable_reason


class AdapterRegistry:
    """
    Thread-safe registry mapping AdapterType → AdapterRegistration.

    All mutations happen at startup; no locking is needed during test
    execution (read-only access after initialisation).
    """

    def __init__(self) -> None:
        self._registrations: dict[AdapterType, AdapterRegistration] = {}

    def register(
        self,
        adapter_type: AdapterType,
        factory: AdapterFactory,
        supported_technologies: list[ApplicationTechnology],
        check_availability: bool = True,
    ) -> None:
        """
        Register an adapter factory.

        Parameters
        ----------
        adapter_type:
            Unique adapter identifier.
        factory:
            Zero-argument callable that creates an initialised adapter instance.
        supported_technologies:
            List of ApplicationTechnology values the adapter handles.
        check_availability:
            If True, instantiate the adapter to call ``is_available()``.
            Set to False when registering adapters in unit tests.
        """
        available = True
        reason: str | None = None

        if check_availability:
            try:
                instance = factory()
                available = instance.is_available()
                if not available:
                    reason = f"Adapter '{adapter_type.value}' reported not available"
            except Exception as exc:
                available = False
                reason = str(exc)

        registration = AdapterRegistration(
            adapter_type=adapter_type,
            factory=factory,
            supported_technologies=supported_technologies,
            available=available,
            unavailable_reason=reason,
        )
        self._registrations[adapter_type] = registration

        status = "available" if available else f"unavailable ({reason})"
        _log.info(
            "adapter_registered",
            adapter_type=adapter_type.value,
            technologies=[t.value for t in supported_technologies],
            status=status,
        )

    def get(self, adapter_type: AdapterType) -> AdapterRegistration | None:
        """Return the registration for ``adapter_type``, or None if not registered."""
        return self._registrations.get(adapter_type)

    def get_or_raise(self, adapter_type: AdapterType) -> AdapterRegistration:
        """Return the registration for ``adapter_type`` or raise ``AdapterNotAvailableException``."""
        from desktop_automation_platform.core.exceptions import AdapterNotAvailableException

        reg = self._registrations.get(adapter_type)
        if reg is None:
            raise AdapterNotAvailableException(
                adapter_type=adapter_type.value,
                reason="Adapter is not registered. Ensure the adapter package is installed.",
            )
        if not reg.available:
            raise AdapterNotAvailableException(
                adapter_type=adapter_type.value,
                reason=reg.unavailable_reason or "Adapter reported unavailable",
            )
        return reg

    def find_for_technology(
        self,
        technology: ApplicationTechnology,
    ) -> list[AdapterRegistration]:
        """
        Return all available registrations that support ``technology``,
        ordered by adapter priority (FlaUI → pywinauto → others).
        """
        matches = [
            reg
            for reg in self._registrations.values()
            if technology in reg.supported_technologies and reg.available
        ]
        return sorted(matches, key=lambda r: _ADAPTER_PRIORITY.get(r.adapter_type, 99))

    def all_available(self) -> list[AdapterRegistration]:
        """Return all registrations where ``available`` is True."""
        return [r for r in self._registrations.values() if r.available]

    def all_registrations(self) -> list[AdapterRegistration]:
        """Return all registrations regardless of availability."""
        return list(self._registrations.values())

    def is_registered(self, adapter_type: AdapterType) -> bool:
        return adapter_type in self._registrations

    def unregister(self, adapter_type: AdapterType) -> None:
        """Remove a registration (primarily for testing)."""
        self._registrations.pop(adapter_type, None)

    def clear(self) -> None:
        """Remove all registrations (primarily for testing)."""
        self._registrations.clear()

    def diagnostic_report(self) -> str:
        """Return a human-readable summary of all registered adapters."""
        lines = ["Adapter Registry Status", "=" * 40]
        for reg in self._registrations.values():
            status = "✓ available" if reg.available else f"✗ {reg.unavailable_reason}"
            techs = ", ".join(t.value for t in reg.supported_technologies)
            lines.append(f"  {reg.adapter_type.value:30s} [{status}]  technologies: {techs}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Priority table — determines adapter preference when multiple adapters
# support the same technology (lower number = higher priority)
# ---------------------------------------------------------------------------

_ADAPTER_PRIORITY: dict[AdapterType, int] = {
    AdapterType.FLAUI: 1,
    AdapterType.PYWINAUTO: 2,
    AdapterType.WINAPPDRIVER: 3,
    AdapterType.JAVA_ACCESS_BRIDGE: 4,
    AdapterType.ELECTRON_PLAYWRIGHT: 5,
    AdapterType.SIKULI_IMAGE: 6,
    AdapterType.AUTOIT: 7,
}
