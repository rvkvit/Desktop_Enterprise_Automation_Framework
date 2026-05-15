"""
YAML configuration loader with Pydantic v2 schema validation.

Responsibilities:
- Read YAML file from disk
- Resolve environment variable references (${VAR_NAME} syntax)
- Validate against PlatformConfig schema
- Surface actionable error messages on validation failure

Environment variable interpolation example::

    application:
      executable: ${CLAIMS_APP_EXE}
      name: Claims Desktop
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from desktop_automation_platform.config.schema import PlatformConfig
from desktop_automation_platform.core.exceptions import (
    InvalidConfigException,
    MissingConfigException,
)

_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


class YamlConfigLoader:
    """
    Loads ``PlatformConfig`` from a YAML file.

    Usage::

        loader = YamlConfigLoader()
        config = loader.load("config/claims.yaml")
    """

    def load(self, config_path: str | Path) -> PlatformConfig:
        """
        Load and validate a YAML configuration file.

        Environment variables referenced as ``${VAR_NAME}`` in any string
        value are expanded before schema validation.
        """
        path = Path(config_path)
        if not path.exists():
            raise MissingConfigException(str(path))

        raw_text = path.read_text(encoding="utf-8")
        interpolated = self._interpolate_env_vars(raw_text, path)

        try:
            raw_dict: dict[str, Any] = yaml.safe_load(interpolated) or {}
        except yaml.YAMLError as exc:
            raise InvalidConfigException(
                path=str(path),
                validation_errors=[f"YAML parse error: {exc}"],
            ) from exc

        return self._validate(raw_dict, str(path))

    def load_from_dict(self, data: dict[str, Any]) -> PlatformConfig:
        """Load config from a pre-parsed dictionary (no file I/O)."""
        return self._validate(data, path="<dict>")

    def load_from_string(self, yaml_text: str) -> PlatformConfig:
        """Load config from a raw YAML string (useful for testing)."""
        try:
            raw_dict: dict[str, Any] = yaml.safe_load(yaml_text) or {}
        except yaml.YAMLError as exc:
            raise InvalidConfigException(
                path="<string>",
                validation_errors=[f"YAML parse error: {exc}"],
            ) from exc
        return self._validate(raw_dict, path="<string>")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _interpolate_env_vars(text: str, source_path: Path) -> str:
        """
        Replace ``${VAR_NAME}`` references with environment variable values.
        Raises ``InvalidConfigException`` for undefined variables.
        """
        missing: list[str] = []

        def replace(match: re.Match[str]) -> str:
            var_name = match.group(1)
            value = os.environ.get(var_name)
            if value is None:
                missing.append(var_name)
                return match.group(0)  # leave as-is; report below
            return value

        result = _ENV_VAR_PATTERN.sub(replace, text)

        if missing:
            raise InvalidConfigException(
                path=str(source_path),
                validation_errors=[
                    f"Undefined environment variable(s): {', '.join(sorted(missing))}"
                ],
            )
        return result

    @staticmethod
    def _validate(data: dict[str, Any], path: str) -> PlatformConfig:
        """Validate the raw dict against the Pydantic schema."""
        try:
            return PlatformConfig.model_validate(data)
        except ValidationError as exc:
            errors = [
                f"{' -> '.join(str(loc) for loc in e['loc'])}: {e['msg']}"
                for e in exc.errors()
            ]
            raise InvalidConfigException(path=path, validation_errors=errors) from exc
