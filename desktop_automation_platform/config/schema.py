"""
Pydantic v2 configuration schema for the Desktop Automation Platform.

All YAML configuration is validated against these models before being
exposed to the rest of the platform. Field descriptions serve as inline
documentation for YAML authors.

YAML structure::

    framework:
      adapter_mode: auto
      retry_count: 3
      screenshot_on_failure: true
      logging_level: INFO

    application:
      name: Claims Desktop
      executable: C:\\Apps\\claims.exe
      type: auto

    execution:
      timeout: 30
      wait_strategy: explicit

    reporting:
      output_directory: reports
      screenshots_directory: screenshots

    adapters:
      flaui:
        enabled: true
      winappdriver:
        enabled: false
        server_url: http://localhost:4723
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enumerations (schema-level; mirror core.models enums for YAML validation)
# ---------------------------------------------------------------------------


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AdapterMode(str, Enum):
    AUTO = "auto"
    FLAUI = "flaui"
    WINAPPDRIVER = "winappdriver"
    PYWINAUTO = "pywinauto"
    JAVA_ACCESS_BRIDGE = "java_access_bridge"
    SIKULI_IMAGE = "sikuli_image"
    AUTOIT = "autoit"
    ELECTRON_PLAYWRIGHT = "electron_playwright"


class WaitStrategy(str, Enum):
    EXPLICIT = "explicit"
    IMPLICIT = "implicit"
    FLUENT = "fluent"


class ApplicationType(str, Enum):
    AUTO = "auto"
    WPF = "wpf"
    WINFORMS = "winforms"
    WINUI3 = "winui3"
    MAUI = "maui"
    WIN32 = "win32"
    JAVA_SWING = "java_swing"
    QT = "qt"
    ELECTRON = "electron"
    CITRIX = "citrix"
    PACKAGED = "packaged"


# ---------------------------------------------------------------------------
# Sub-configurations
# ---------------------------------------------------------------------------


class FrameworkConfig(BaseModel):
    """Global framework behaviour settings."""

    adapter_mode: AdapterMode = Field(
        default=AdapterMode.AUTO,
        description="Which adapter to use. 'auto' enables technology detection.",
    )
    retry_count: int = Field(
        default=3,
        ge=0,
        le=20,
        description="Number of retry attempts for failed actions.",
    )
    screenshot_on_failure: bool = Field(
        default=True,
        description="Automatically capture a screenshot on action failure.",
    )
    logging_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Minimum log level emitted by the platform.",
    )
    detection_confidence_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum confidence score for automatic technology detection. "
            "Below this threshold the framework requests a manual override."
        ),
    )
    structured_logging: bool = Field(
        default=True,
        description="Emit logs in structured JSON format (disable for human-readable console).",
    )


class ApplicationConfig(BaseModel):
    """Describes the desktop application under test."""

    name: str = Field(description="Human-readable application name (used in reports).")
    executable: str | None = Field(
        default=None,
        description="Absolute path to the application executable.",
    )
    type: ApplicationType = Field(
        default=ApplicationType.AUTO,
        description="Application technology. 'auto' enables runtime detection.",
    )
    window_title: str | None = Field(
        default=None,
        description="Window title used for attach-by-title operations.",
    )
    working_directory: str | None = Field(
        default=None,
        description="Working directory when launching the application.",
    )
    launch_arguments: list[str] = Field(
        default_factory=list,
        description="Command-line arguments passed on launch.",
    )
    launch_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        description="Maximum seconds to wait for the application window to appear.",
    )
    environment: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables injected into the launched process.",
    )

    @field_validator("executable")
    @classmethod
    def executable_must_be_absolute_if_set(cls, v: str | None) -> str | None:
        if v is not None and not Path(v).is_absolute():
            raise ValueError(f"executable must be an absolute path, got: {v!r}")
        return v


class ExecutionConfig(BaseModel):
    """Controls timing and polling behaviour during automation."""

    timeout: float = Field(
        default=30.0,
        gt=0,
        description="Default element wait timeout in seconds.",
    )
    wait_strategy: WaitStrategy = Field(
        default=WaitStrategy.EXPLICIT,
        description="Waiting strategy: explicit (recommended), implicit, or fluent.",
    )
    implicit_wait: float = Field(
        default=0.0,
        ge=0,
        description="Implicit wait in seconds (only effective when wait_strategy=implicit).",
    )
    poll_interval: float = Field(
        default=0.5,
        gt=0,
        description="Polling interval in seconds between retry/wait checks.",
    )
    action_delay: float = Field(
        default=0.0,
        ge=0,
        description="Fixed delay inserted between consecutive actions (for slow AUTs).",
    )


class ReportingConfig(BaseModel):
    """Controls report output location and content."""

    output_directory: str = Field(
        default="reports",
        description="Root directory for all report artefacts.",
    )
    screenshots_directory: str = Field(
        default="reports/screenshots",
        description="Directory for captured screenshots.",
    )
    include_screenshots: bool = Field(
        default=True,
        description="Embed screenshots in reports.",
    )
    include_execution_trace: bool = Field(
        default=True,
        description="Include full keyword-level execution trace in reports.",
    )
    include_locator_resolution_path: bool = Field(
        default=True,
        description="Record which locator strategy succeeded for each action.",
    )
    max_screenshot_age_days: int = Field(
        default=30,
        ge=1,
        description="Purge screenshots older than this many days.",
    )


class FlaUIAdapterConfig(BaseModel):
    """FlaUI adapter-specific settings."""

    enabled: bool = True
    automation_type: str = Field(
        default="UIA3",
        description="UIA2 or UIA3. UIA3 is recommended for WPF/WinUI3.",
    )
    highlight_elements: bool = Field(
        default=False,
        description="Highlight matched elements for debugging (slows execution).",
    )


class WinAppDriverAdapterConfig(BaseModel):
    """WinAppDriver adapter-specific settings."""

    enabled: bool = False
    server_url: str = Field(
        default="http://localhost:4723",
        description="WinAppDriver server URL.",
    )
    platform_name: str = "Windows"
    platform_version: str = "10"


class PywinautoAdapterConfig(BaseModel):
    """pywinauto adapter-specific settings."""

    enabled: bool = True
    backend: str = Field(
        default="uia",
        description="pywinauto backend: 'uia' (UIA) or 'win32' (Win32).",
    )


class JavaAccessBridgeAdapterConfig(BaseModel):
    """Java Access Bridge adapter-specific settings."""

    enabled: bool = True
    java_home: str | None = Field(
        default=None,
        description="Override JAVA_HOME for the JAB bridge.",
    )


class SikuliImageAdapterConfig(BaseModel):
    """Sikuli image-based adapter settings (for Citrix / RDP / screenshot-only AUTs)."""

    enabled: bool = True
    similarity_threshold: float = Field(
        default=0.9,
        ge=0.1,
        le=1.0,
        description="Minimum image similarity score (0.0–1.0) for template matching.",
    )
    screenshot_directory: str = Field(
        default="image_templates",
        description="Directory containing template images for matching.",
    )


class ElectronPlaywrightAdapterConfig(BaseModel):
    """Playwright-based Electron adapter settings."""

    enabled: bool = True
    browser_type: str = Field(
        default="chromium",
        description="Playwright browser type backing the Electron WebView.",
    )
    headless: bool = False
    devtools: bool = False


class AdaptersConfig(BaseModel):
    """Per-adapter configuration blocks."""

    flaui: FlaUIAdapterConfig = Field(default_factory=FlaUIAdapterConfig)
    winappdriver: WinAppDriverAdapterConfig = Field(
        default_factory=WinAppDriverAdapterConfig
    )
    pywinauto: PywinautoAdapterConfig = Field(default_factory=PywinautoAdapterConfig)
    java_access_bridge: JavaAccessBridgeAdapterConfig = Field(
        default_factory=JavaAccessBridgeAdapterConfig
    )
    sikuli_image: SikuliImageAdapterConfig = Field(
        default_factory=SikuliImageAdapterConfig
    )
    electron_playwright: ElectronPlaywrightAdapterConfig = Field(
        default_factory=ElectronPlaywrightAdapterConfig
    )


# ---------------------------------------------------------------------------
# AI extensibility stubs (Phase 1 — design contracts only, no implementation)
# ---------------------------------------------------------------------------


class AIExtensibilityConfig(BaseModel):
    """
    Extension points for AI-assisted automation capabilities.
    These fields define the contract; implementations arrive in a future phase.
    """

    locator_optimization_enabled: bool = False
    intelligent_healing_enabled: bool = False
    auto_test_generation_enabled: bool = False
    root_cause_analysis_enabled: bool = False
    model_endpoint: str | None = Field(
        default=None,
        description="AI model endpoint URL (when AI features are enabled).",
    )
    api_key_env_var: str | None = Field(
        default=None,
        description="Environment variable name holding the AI API key.",
    )


# ---------------------------------------------------------------------------
# Root platform config
# ---------------------------------------------------------------------------


class PlatformConfig(BaseModel):
    """
    Root configuration model for the Desktop Automation Platform.
    All YAML configuration is validated against this model.
    """

    framework: FrameworkConfig = Field(default_factory=FrameworkConfig)
    application: ApplicationConfig
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)
    adapters: AdaptersConfig = Field(default_factory=AdaptersConfig)
    ai: AIExtensibilityConfig = Field(default_factory=AIExtensibilityConfig)
    custom: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary key-value pairs for project-specific extensions.",
    )

    @model_validator(mode="after")
    def validate_cross_field_constraints(self) -> "PlatformConfig":
        # When adapter_mode is not AUTO, ensure the corresponding adapter is enabled
        mode = self.framework.adapter_mode
        adapter_map = {
            AdapterMode.FLAUI: self.adapters.flaui.enabled,
            AdapterMode.WINAPPDRIVER: self.adapters.winappdriver.enabled,
            AdapterMode.PYWINAUTO: self.adapters.pywinauto.enabled,
            AdapterMode.JAVA_ACCESS_BRIDGE: self.adapters.java_access_bridge.enabled,
            AdapterMode.SIKULI_IMAGE: self.adapters.sikuli_image.enabled,
            AdapterMode.ELECTRON_PLAYWRIGHT: self.adapters.electron_playwright.enabled,
        }
        if mode != AdapterMode.AUTO and not adapter_map.get(mode, True):
            raise ValueError(
                f"adapter_mode is '{mode.value}' but the corresponding adapter "
                f"is disabled under adapters.{mode.value}.enabled"
            )
        return self

    model_config = {"extra": "forbid"}
