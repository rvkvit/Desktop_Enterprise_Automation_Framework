"""
ILocatorScanner — UI tree introspection and locator discovery.

Implementations walk the live accessibility tree of a running application
and produce ``ElementInfo`` snapshots used by the locator discovery engine
to auto-generate YAML locator repositories.

Scanner output format::

    # locators/claims_desktop.yaml
    LOGIN_BUTTON:
      primary:
        strategy: automation_id
        value: LoginButton
      fallbacks:
        - strategy: name
          value: Login
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from desktop_automation_platform.core.models import (
    ApplicationSession,
    ElementInfo,
    UnifiedLocator,
)


class ILocatorScanner(ABC):
    """
    Inspects a live desktop application's UI accessibility tree and
    produces locator artefacts (ElementInfo / YAML / Robot resource).
    """

    @abstractmethod
    def scan_application(
        self,
        session: ApplicationSession,
        max_depth: int = 10,
    ) -> list[ElementInfo]:
        """
        Walk the entire UI tree of the application attached to ``session``.

        Returns a flat list of ``ElementInfo`` with parent references
        preserved via ``parent_automation_id``.
        ``max_depth`` caps the recursion to avoid pathological trees.
        """
        ...

    @abstractmethod
    def scan_element(
        self,
        session: ApplicationSession,
        locator: UnifiedLocator,
        max_depth: int = 5,
    ) -> list[ElementInfo]:
        """
        Walk the subtree rooted at the element resolved by ``locator``.
        Useful for scanning a dialog or container in isolation.
        """
        ...

    @abstractmethod
    def export_yaml(
        self,
        elements: list[ElementInfo],
        output_path: str,
        overwrite: bool = False,
    ) -> str:
        """
        Write a YAML locator repository from the given ``ElementInfo`` list.
        Returns the absolute path of the written file.
        Raises ``FileExistsError`` if ``output_path`` exists and not
        ``overwrite``.
        """
        ...

    @abstractmethod
    def export_robot_resource(
        self,
        elements: list[ElementInfo],
        output_path: str,
        overwrite: bool = False,
    ) -> str:
        """
        Write a Robot Framework ``.resource`` file with variable definitions
        for each discovered element.
        Returns the absolute path of the written file.
        """
        ...
