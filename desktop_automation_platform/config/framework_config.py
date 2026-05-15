"""
YamlConfigManager — concrete IConfigManager implementation.

Wraps YamlConfigLoader with hot-reload, dotted-key override merging,
and a singleton access pattern suitable for injection into the DI container.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from desktop_automation_platform.config.schema import PlatformConfig
from desktop_automation_platform.config.yaml_loader import YamlConfigLoader
from desktop_automation_platform.core.exceptions import MissingConfigException
from desktop_automation_platform.core.interfaces.config_manager import IConfigManager


def _set_nested(d: dict[str, Any], dotted_key: str, value: Any) -> None:
    """Set a value in a nested dict using a dotted key path."""
    keys = dotted_key.split(".")
    current = d
    for key in keys[:-1]:
        current = current.setdefault(key, {})
    current[keys[-1]] = value


class YamlConfigManager(IConfigManager):
    """
    IConfigManager implementation backed by YAML files.

    Thread-safety note: ``reload`` and ``merge_overrides`` are not
    thread-safe by design — configuration changes mid-run are rare and
    callers are expected to use external synchronisation if needed.
    """

    def __init__(self, loader: YamlConfigLoader | None = None) -> None:
        self._loader = loader or YamlConfigLoader()
        self._config: PlatformConfig | None = None
        self._config_path: Path | None = None
        self._raw_dict: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # IConfigManager
    # ------------------------------------------------------------------

    def load(self, config_path: str | Path) -> PlatformConfig:
        path = Path(config_path)
        self._config_path = path
        config = self._loader.load(path)
        self._config = config
        # Cache raw dict for override merging
        import yaml  # noqa: PLC0415

        self._raw_dict = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return config

    def load_from_dict(self, data: dict[str, Any]) -> PlatformConfig:
        self._raw_dict = copy.deepcopy(data)
        self._config = self._loader.load_from_dict(data)
        self._config_path = None
        return self._config

    def get_config(self) -> PlatformConfig:
        if self._config is None:
            raise MissingConfigException(path="<not loaded>")
        return self._config

    def reload(self) -> PlatformConfig:
        if self._config_path is None:
            raise MissingConfigException(
                path="<no path — config was loaded from dict, cannot reload>"
            )
        return self.load(self._config_path)

    def merge_overrides(self, overrides: dict[str, Any]) -> PlatformConfig:
        """
        Apply dotted-key overrides to the last loaded raw dict and re-validate.

        Example::
            manager.merge_overrides({
                "framework.retry_count": 5,
                "execution.timeout": 60,
            })
        """
        merged = copy.deepcopy(self._raw_dict)
        for dotted_key, value in overrides.items():
            _set_nested(merged, dotted_key, value)
        self._config = self._loader.load_from_dict(merged)
        return self._config

    @property
    def config_path(self) -> Path | None:
        return self._config_path
