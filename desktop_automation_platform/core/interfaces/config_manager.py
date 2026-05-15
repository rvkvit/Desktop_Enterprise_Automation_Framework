"""
IConfigManager — configuration loading, merging, and access contract.

The config manager owns the full lifecycle of framework configuration:
parsing YAML, validating against the Pydantic schema, merging environment
variable overrides, and exposing typed access to all config sections.

Design: all framework code receives the config manager via DI — never reads
YAML or environment variables directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from desktop_automation_platform.config.schema import PlatformConfig


class IConfigManager(ABC):
    """
    Loads, validates, and exposes platform configuration.
    Supports hot-reload for CI/CD environments where config may change
    between test suites.
    """

    @abstractmethod
    def load(self, config_path: str | Path) -> "PlatformConfig":
        """
        Load and validate a YAML config file.

        Raises ``InvalidConfigException`` on schema violations.
        Raises ``MissingConfigException`` if the file does not exist.
        Returns the validated ``PlatformConfig`` and caches it internally.
        """
        ...

    @abstractmethod
    def load_from_dict(self, data: dict[str, Any]) -> "PlatformConfig":
        """
        Load config from a pre-parsed dictionary (useful in tests and
        programmatic usage without a file on disk).
        """
        ...

    @abstractmethod
    def get_config(self) -> "PlatformConfig":
        """
        Return the currently loaded config.
        Raises ``MissingConfigException`` if no config has been loaded yet.
        """
        ...

    @abstractmethod
    def reload(self) -> "PlatformConfig":
        """
        Reload the config from the same path used in the last ``load`` call.
        Useful for long-running processes that need to pick up file changes.
        """
        ...

    @abstractmethod
    def merge_overrides(self, overrides: dict[str, Any]) -> "PlatformConfig":
        """
        Apply a dict of dotted-key overrides to the current config and
        return the merged result without persisting to disk.

        Example::
            manager.merge_overrides({"framework.retry_count": 5})
        """
        ...

    @property
    @abstractmethod
    def config_path(self) -> Path | None:
        """Path of the last loaded config file, or None if loaded from dict."""
        ...
