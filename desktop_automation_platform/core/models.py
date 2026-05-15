"""
Core domain models for the Desktop Automation Platform.

All models are immutable-by-convention dataclasses shared across every module.
No business logic lives here — this is pure data shape.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ApplicationTechnology(str, Enum):
    """Detected technology stack of the desktop application under test."""

    WPF = "wpf"
    WINFORMS = "winforms"
    WINUI3 = "winui3"
    MAUI = "maui"
    WIN32 = "win32"
    JAVA_SWING = "java_swing"
    JAVA_AWT = "java_awt"
    QT = "qt"
    ELECTRON = "electron"
    CITRIX = "citrix"
    RDP = "rdp"
    PACKAGED = "packaged"          # MSIX / Windows Store
    UWP = "uwp"                    # Universal Windows Platform
    MFC = "mfc"                    # Microsoft Foundation Classes (C++)
    UNKNOWN = "unknown"


class LocatorStrategy(str, Enum):
    """
    Framework-neutral locator strategies.

    Adapters translate these to their native engine's locator syntax.
    Adding a new strategy here requires updating every LocatorTranslator
    implementation (enforced by the ABC).
    """

    AUTOMATION_ID = "automation_id"       # UI Automation AutomationId
    NAME = "name"                          # Control name / text
    CLASS_NAME = "class_name"              # Win32 class / .NET type name
    CONTROL_TYPE = "control_type"          # UIA ControlType (Button, Edit …)
    XPATH = "xpath"                        # XPath expression (JAB, Playwright)
    IMAGE = "image"                        # Template image path (Sikuli / CV)
    ACCESSIBILITY_ID = "accessibility_id"  # macOS / ATK accessibility ID
    CSS_SELECTOR = "css_selector"          # CSS (Playwright / Electron)
    TAG_NAME = "tag_name"                  # HTML tag (Playwright / Electron)
    TEXT = "text"                          # Exact inner text
    PARTIAL_TEXT = "partial_text"          # Partial inner text
    COORDINATES = "coordinates"            # Absolute / relative pixel coords
    RUNTIME_ID = "runtime_id"              # UIA RuntimeId (last-resort)


class AdapterType(str, Enum):
    """Registered adapter identifiers."""

    FLAUI = "flaui"
    WINAPPDRIVER = "winappdriver"
    PYWINAUTO = "pywinauto"
    JAVA_ACCESS_BRIDGE = "java_access_bridge"
    SIKULI_IMAGE = "sikuli_image"
    AUTOIT = "autoit"
    ELECTRON_PLAYWRIGHT = "electron_playwright"
    AUTO = "auto"            # Resolved at runtime by the detector


class ActionStatus(str, Enum):
    """Outcome of a single automation action."""

    SUCCESS = "success"
    FAILED = "failed"
    ELEMENT_NOT_FOUND = "element_not_found"
    TIMEOUT = "timeout"
    RECOVERED = "recovered"   # Succeeded after fallback / recovery
    SKIPPED = "skipped"


class SessionState(str, Enum):
    """Lifecycle state of an automation session."""

    INITIALIZING = "initializing"
    ACTIVE = "active"
    RECOVERING = "recovering"
    CLOSED = "closed"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Locator models
# ---------------------------------------------------------------------------


@dataclass
class LocatorDefinition:
    """
    A single locator probe: one strategy + one value.

    ``timeout`` overrides the framework-level wait when present.
    ``index``   selects the nth match when a strategy returns multiple hits.
    """

    strategy: LocatorStrategy
    value: str
    timeout: float | None = None
    index: int | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.strategy, str):
            self.strategy = LocatorStrategy(self.strategy)


@dataclass
class UnifiedLocator:
    """
    Framework-neutral locator with cascading fallback chain.

    Adapters attempt ``primary`` first, then each ``fallback`` in order.
    The locator_engine's self-healing layer tracks resolution history to
    promote successful fallbacks to primary over time.

    YAML example (locator repository)::

        LOGIN_BUTTON:
          primary:
            strategy: automation_id
            value: LoginButton
          fallbacks:
            - strategy: name
              value: Login
            - strategy: image
              value: login_button.png
    """

    name: str
    primary: LocatorDefinition
    fallbacks: list[LocatorDefinition] = field(default_factory=list)
    scope: str | None = None           # Parent element locator name
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "UnifiedLocator":
        """Deserialise from a YAML-parsed dict (locator repository format)."""
        primary_raw = data["primary"]
        primary = LocatorDefinition(
            strategy=LocatorStrategy(primary_raw["strategy"]),
            value=primary_raw["value"],
            timeout=primary_raw.get("timeout"),
            index=primary_raw.get("index"),
            description=primary_raw.get("description"),
        )
        fallbacks: list[LocatorDefinition] = []
        for fb in data.get("fallbacks", []):
            fallbacks.append(
                LocatorDefinition(
                    strategy=LocatorStrategy(fb["strategy"]),
                    value=fb["value"],
                    timeout=fb.get("timeout"),
                    index=fb.get("index"),
                    description=fb.get("description"),
                )
            )
        return cls(
            name=name,
            primary=primary,
            fallbacks=fallbacks,
            scope=data.get("scope"),
            metadata=data.get("metadata", {}),
        )

    def all_strategies(self) -> list[LocatorDefinition]:
        """Primary followed by all fallbacks, in resolution order."""
        return [self.primary, *self.fallbacks]


# ---------------------------------------------------------------------------
# Application / session models
# ---------------------------------------------------------------------------


@dataclass
class ApplicationInfo:
    """Descriptor for the desktop application under test."""

    name: str
    executable: str | None = None
    process_id: int | None = None
    window_title: str | None = None
    technology: ApplicationTechnology | None = None
    working_directory: str | None = None
    launch_arguments: list[str] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ApplicationSession:
    """
    Runtime handle for a live desktop automation session.

    ``native_session`` holds the adapter-specific connection object
    (e.g. FlaUI ``Application``, WAD ``WebDriver``, Playwright ``Page``).
    Platform code must never inspect ``native_session`` directly — all
    interaction goes through the adapter interface.
    """

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    app_info: ApplicationInfo | None = None
    adapter_type: AdapterType | None = None
    state: SessionState = SessionState.INITIALIZING
    started_at: datetime = field(default_factory=datetime.utcnow)
    native_session: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_active(self) -> bool:
        return self.state == SessionState.ACTIVE

    def mark_active(self) -> None:
        self.state = SessionState.ACTIVE

    def mark_closed(self) -> None:
        self.state = SessionState.CLOSED

    def mark_error(self) -> None:
        self.state = SessionState.ERROR

    def mark_recovering(self) -> None:
        self.state = SessionState.RECOVERING


# ---------------------------------------------------------------------------
# Action / result models
# ---------------------------------------------------------------------------


@dataclass
class ActionResult:
    """
    Structured outcome of a single keyword execution.

    Carries enough diagnostic information for the reporter to render a
    complete execution trace without accessing any external state.
    """

    action: str
    status: ActionStatus
    duration_ms: float = 0.0
    locator_used: LocatorDefinition | None = None
    locator_attempts: list[LocatorDefinition] = field(default_factory=list)
    error_message: str | None = None
    screenshot_path: str | None = None
    recovery_applied: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def is_success(self) -> bool:
        return self.status in (ActionStatus.SUCCESS, ActionStatus.RECOVERED)

    def raise_if_failed(self) -> None:
        from desktop_automation_platform.core.exceptions import AdapterOperationException

        if not self.is_success():
            raise AdapterOperationException(
                action=self.action,
                message=self.error_message or "Action failed",
                screenshot_path=self.screenshot_path,
            )


# ---------------------------------------------------------------------------
# Element introspection model (used by scanner + locator engine)
# ---------------------------------------------------------------------------


@dataclass
class ElementInfo:
    """
    Snapshot of a UI element's accessibility properties.

    Populated by the LocatorScanner implementations; consumed by the
    locator discovery engine to generate locator repositories.
    """

    automation_id: str | None = None
    name: str | None = None
    class_name: str | None = None
    control_type: str | None = None
    is_enabled: bool = True
    is_visible: bool = True
    bounding_rect: dict[str, int] | None = None   # {x, y, width, height}
    parent_automation_id: str | None = None
    children: list["ElementInfo"] = field(default_factory=list)
    supported_patterns: list[str] = field(default_factory=list)
    xpath: str | None = None
    runtime_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Detector models
# ---------------------------------------------------------------------------


@dataclass
class DetectionResult:
    """
    Result of automated application technology detection.

    ``confidence`` is a 0.0–1.0 score derived from the number and weight
    of evidence signals matched during inspection.
    """

    technology: ApplicationTechnology
    confidence: float
    recommended_adapter: AdapterType
    evidence: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Recovery models
# ---------------------------------------------------------------------------


@dataclass
class RecoveryContext:
    """Input payload passed to every recovery strategy."""

    session: ApplicationSession
    failed_action: str
    error_message: str
    attempt_number: int
    locator: UnifiedLocator | None = None
    action_result: ActionResult | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryResult:
    """Outcome of a recovery attempt."""

    recovered: bool
    strategy_used: str | None = None
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
