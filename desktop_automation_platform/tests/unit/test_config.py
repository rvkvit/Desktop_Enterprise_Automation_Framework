"""
Unit tests for config schema validation, YAML loading, and config manager.
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest

from desktop_automation_platform.config.framework_config import YamlConfigManager
from desktop_automation_platform.config.schema import (
    AdapterMode,
    ApplicationConfig,
    FrameworkConfig,
    LogLevel,
    PlatformConfig,
    WaitStrategy,
)
from desktop_automation_platform.config.yaml_loader import YamlConfigLoader
from desktop_automation_platform.core.exceptions import (
    InvalidConfigException,
    MissingConfigException,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def loader() -> YamlConfigLoader:
    return YamlConfigLoader()


@pytest.fixture
def manager() -> YamlConfigManager:
    return YamlConfigManager()


@pytest.fixture
def minimal_yaml() -> str:
    return textwrap.dedent(
        """
        application:
          name: Test App
          executable: C:\\\\Apps\\\\test.exe
        """
    )


@pytest.fixture
def full_yaml() -> str:
    return textwrap.dedent(
        """
        framework:
          adapter_mode: auto
          retry_count: 5
          screenshot_on_failure: true
          logging_level: DEBUG

        application:
          name: Claims Desktop
          executable: C:\\\\Apps\\\\claims.exe
          type: wpf
          window_title: Claims Processing

        execution:
          timeout: 45
          wait_strategy: explicit
          poll_interval: 0.3

        reporting:
          output_directory: reports/claims
          screenshots_directory: reports/claims/screenshots
        """
    )


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestPlatformConfigSchema:
    def test_minimal_config_with_defaults(self) -> None:
        config = PlatformConfig(
            application=ApplicationConfig(name="My App")
        )
        assert config.framework.adapter_mode == AdapterMode.AUTO
        assert config.framework.retry_count == 3
        assert config.framework.screenshot_on_failure is True
        assert config.framework.logging_level == LogLevel.INFO
        assert config.execution.timeout == 30.0
        assert config.execution.wait_strategy == WaitStrategy.EXPLICIT

    def test_retry_count_bounds(self) -> None:
        with pytest.raises(Exception):
            PlatformConfig(
                application=ApplicationConfig(name="App"),
                framework=FrameworkConfig(retry_count=-1),
            )

    def test_retry_count_upper_bound(self) -> None:
        with pytest.raises(Exception):
            PlatformConfig(
                application=ApplicationConfig(name="App"),
                framework=FrameworkConfig(retry_count=21),
            )

    def test_executable_must_be_absolute(self) -> None:
        with pytest.raises(Exception):
            PlatformConfig(
                application=ApplicationConfig(
                    name="App",
                    executable="relative/path/app.exe",
                )
            )

    def test_adapter_mode_disabled_adapter_raises(self) -> None:
        from desktop_automation_platform.config.schema import (
            AdaptersConfig,
            WinAppDriverAdapterConfig,
        )

        with pytest.raises(Exception):
            PlatformConfig(
                application=ApplicationConfig(name="App"),
                framework=FrameworkConfig(adapter_mode=AdapterMode.WINAPPDRIVER),
                adapters=AdaptersConfig(
                    winappdriver=WinAppDriverAdapterConfig(enabled=False)
                ),
            )

    def test_detection_confidence_threshold_bounds(self) -> None:
        with pytest.raises(Exception):
            PlatformConfig(
                application=ApplicationConfig(name="App"),
                framework=FrameworkConfig(detection_confidence_threshold=1.5),
            )


# ---------------------------------------------------------------------------
# YAML loader tests
# ---------------------------------------------------------------------------


class TestYamlConfigLoader:
    def test_load_minimal_yaml_string(
        self, loader: YamlConfigLoader, minimal_yaml: str
    ) -> None:
        config = loader.load_from_string(minimal_yaml)
        assert config.application.name == "Test App"

    def test_load_full_yaml_string(
        self, loader: YamlConfigLoader, full_yaml: str
    ) -> None:
        config = loader.load_from_string(full_yaml)
        assert config.application.name == "Claims Desktop"
        assert config.framework.retry_count == 5
        assert config.framework.logging_level == LogLevel.DEBUG
        assert config.execution.timeout == 45.0

    def test_load_from_file(
        self, loader: YamlConfigLoader, minimal_yaml: str, tmp_path: Path
    ) -> None:
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(minimal_yaml)
        config = loader.load(yaml_file)
        assert config.application.name == "Test App"

    def test_missing_file_raises(self, loader: YamlConfigLoader) -> None:
        with pytest.raises(MissingConfigException) as exc_info:
            loader.load("/nonexistent/path/config.yaml")
        assert "/nonexistent/path/config.yaml" in exc_info.value.message

    def test_invalid_yaml_raises_parse_error(
        self, loader: YamlConfigLoader, tmp_path: Path
    ) -> None:
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("{{{{invalid yaml}}}")
        with pytest.raises(InvalidConfigException):
            loader.load(bad_yaml)

    def test_schema_violation_raises(self, loader: YamlConfigLoader) -> None:
        with pytest.raises(InvalidConfigException) as exc_info:
            loader.load_from_string(
                "application:\n  name: App\nframework:\n  retry_count: 999\n"
            )
        assert exc_info.value.validation_errors

    def test_env_var_interpolation(
        self, loader: YamlConfigLoader, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("APP_EXE", "C:\\Apps\\test.exe")
        yaml_text = "application:\n  name: App\n  executable: ${APP_EXE}\n"
        config = loader.load_from_string(yaml_text)
        assert config.application.executable == "C:\\Apps\\test.exe"

    def test_undefined_env_var_raises(
        self, loader: YamlConfigLoader, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("UNDEFINED_VAR", raising=False)
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("application:\n  name: App\n  executable: ${UNDEFINED_VAR}\n")
        with pytest.raises(InvalidConfigException) as exc_info:
            loader.load(yaml_file)
        assert "UNDEFINED_VAR" in exc_info.value.message

    def test_missing_required_field_raises(self, loader: YamlConfigLoader) -> None:
        with pytest.raises(InvalidConfigException):
            # 'application' key is required
            loader.load_from_string("framework:\n  retry_count: 3\n")


# ---------------------------------------------------------------------------
# Config manager tests
# ---------------------------------------------------------------------------


class TestYamlConfigManager:
    def test_load_and_get(self, manager: YamlConfigManager, tmp_path: Path) -> None:
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("application:\n  name: My App\n")
        config = manager.load(yaml_file)
        assert manager.get_config() is config

    def test_get_before_load_raises(self, manager: YamlConfigManager) -> None:
        with pytest.raises(MissingConfigException):
            manager.get_config()

    def test_reload(self, manager: YamlConfigManager, tmp_path: Path) -> None:
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("application:\n  name: Version 1\n")
        manager.load(yaml_file)

        yaml_file.write_text("application:\n  name: Version 2\n")
        config = manager.reload()
        assert config.application.name == "Version 2"

    def test_merge_overrides(self, manager: YamlConfigManager) -> None:
        manager.load_from_dict({"application": {"name": "App"}})
        config = manager.merge_overrides({"framework.retry_count": 7})
        assert config.framework.retry_count == 7

    def test_config_path_is_none_for_dict_load(
        self, manager: YamlConfigManager
    ) -> None:
        manager.load_from_dict({"application": {"name": "App"}})
        assert manager.config_path is None

    def test_config_path_set_after_file_load(
        self, manager: YamlConfigManager, tmp_path: Path
    ) -> None:
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("application:\n  name: App\n")
        manager.load(yaml_file)
        assert manager.config_path == yaml_file
