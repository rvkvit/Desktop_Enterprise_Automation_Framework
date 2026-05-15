"""
Locator repository — YAML loading and UnifiedLocator access.

A locator repository is a YAML file that maps symbolic element names to
their UnifiedLocator definitions.  Tests reference elements by name only;
the underlying strategies are opaque to the test author.

YAML format example (locators/claims_login.yaml)::

    LOGIN_BUTTON:
      primary:
        strategy: automation_id
        value: LoginButton
        timeout: 10
      fallbacks:
        - strategy: name
          value: Login
        - strategy: image
          value: login_button.png

    USERNAME_FIELD:
      primary:
        strategy: automation_id
        value: txtUsername
      scope: LOGIN_PANEL

Usage::

    repo = LocatorRepository.from_yaml("locators/claims_login.yaml")
    locator = repo.get("LOGIN_BUTTON")
    adapter.click(locator, session)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from desktop_automation_platform.core.models import UnifiedLocator


class LocatorRepository:
    """
    Named collection of UnifiedLocators loaded from a YAML repository file.

    Repositories are composable — merge multiple files for a page-object
    pattern::

        repo = LocatorRepository.merge(
            LocatorRepository.from_yaml("login.yaml"),
            LocatorRepository.from_yaml("dashboard.yaml"),
        )
    """

    def __init__(self, locators: dict[str, UnifiedLocator], source: str = "<dict>") -> None:
        self._locators = locators
        self._source = source

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def from_yaml(cls, yaml_path: str | Path) -> "LocatorRepository":
        """Load a locator repository from a YAML file."""
        path = Path(yaml_path)
        if not path.exists():
            raise FileNotFoundError(f"Locator repository not found: {path}")
        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls._from_dict(raw, source=str(path))

    @classmethod
    def from_directory(cls, directory: str | Path, namespace_by_folder: bool = True) -> "LocatorRepository":
        """Load and merge all *.yaml locator files found under ``directory``.

        Files in subdirectories get a ``SUBFOLDER.`` namespace prefix (the
        immediate parent folder name, uppercased).  Files placed directly in
        the root are loaded without a prefix (backward compatible).

        Example layout::

            screens/
              notepad/locators.yaml   → NOTEPAD.TEXT_AREA
              login/locators.yaml     → LOGIN.USERNAME_FIELD
            shared_locators.yaml      → SHARED_BUTTON  (no prefix)
        """
        root = Path(directory)
        if not root.exists():
            raise FileNotFoundError(f"Locator directory not found: {root}")

        repos: list["LocatorRepository"] = []
        for yaml_file in sorted(root.rglob("*.yaml")):
            raw: dict[str, Any] = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
            relative = yaml_file.relative_to(root)
            if namespace_by_folder and len(relative.parts) > 1:
                namespace = relative.parts[0].upper()
                namespaced = {f"{namespace}.{k}": v for k, v in raw.items()}
            else:
                namespaced = raw
            repos.append(cls._from_dict(namespaced, source=str(yaml_file)))

        if not repos:
            return cls({}, source=str(root))
        return cls.merge(*repos)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LocatorRepository":
        """Load a locator repository from a pre-parsed dictionary."""
        return cls._from_dict(data, source="<dict>")

    @classmethod
    def _from_dict(cls, data: dict[str, Any], source: str) -> "LocatorRepository":
        locators: dict[str, UnifiedLocator] = {}
        for name, definition in data.items():
            try:
                locators[name] = UnifiedLocator.from_dict(name, definition)
            except (KeyError, ValueError) as exc:
                raise ValueError(
                    f"Invalid locator definition for '{name}' in {source}: {exc}"
                ) from exc
        return cls(locators=locators, source=source)

    @classmethod
    def merge(cls, *repositories: "LocatorRepository") -> "LocatorRepository":
        """
        Merge multiple repositories into one.
        Later repositories override earlier ones for duplicate names.
        """
        merged: dict[str, UnifiedLocator] = {}
        sources: list[str] = []
        for repo in repositories:
            merged.update(repo._locators)
            sources.append(repo._source)
        return cls(locators=merged, source="; ".join(sources))

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    def get(self, name: str) -> UnifiedLocator:
        """
        Return the locator for ``name``.
        Raises ``KeyError`` if not found (fail fast — missing locators are
        always a configuration error, not a runtime condition).
        """
        try:
            return self._locators[name]
        except KeyError:
            raise KeyError(
                f"Locator '{name}' not found in repository '{self._source}'. "
                f"Available: {sorted(self._locators)}"
            )

    def get_optional(self, name: str) -> UnifiedLocator | None:
        """Return the locator for ``name``, or None if not found."""
        return self._locators.get(name)

    def names(self) -> list[str]:
        """Return sorted list of all locator names in this repository."""
        return sorted(self._locators)

    def __contains__(self, name: str) -> bool:
        return name in self._locators

    def __len__(self) -> int:
        return len(self._locators)

    def __repr__(self) -> str:
        return f"LocatorRepository(source={self._source!r}, count={len(self._locators)})"

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def to_yaml(self, output_path: str | Path, overwrite: bool = False) -> str:
        """Serialise the repository back to YAML."""
        path = Path(output_path)
        if path.exists() and not overwrite:
            raise FileExistsError(f"Output path already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)

        raw: dict[str, Any] = {}
        for name, loc in self._locators.items():
            entry: dict[str, Any] = {
                "primary": {
                    "strategy": loc.primary.strategy.value,
                    "value": loc.primary.value,
                }
            }
            if loc.primary.timeout is not None:
                entry["primary"]["timeout"] = loc.primary.timeout
            if loc.primary.index is not None:
                entry["primary"]["index"] = loc.primary.index
            if loc.fallbacks:
                entry["fallbacks"] = [
                    {
                        "strategy": fb.strategy.value,
                        "value": fb.value,
                        **({"timeout": fb.timeout} if fb.timeout else {}),
                        **({"index": fb.index} if fb.index is not None else {}),
                    }
                    for fb in loc.fallbacks
                ]
            if loc.scope:
                entry["scope"] = loc.scope
            raw[name] = entry

        path.write_text(yaml.dump(raw, sort_keys=True, allow_unicode=True), encoding="utf-8")
        return str(path)
