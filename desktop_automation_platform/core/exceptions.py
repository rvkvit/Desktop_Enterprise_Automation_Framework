"""
Exception hierarchy for the Desktop Automation Platform.

All exceptions carry structured metadata for observability. Never raise
bare Python built-ins from platform code — always use these typed exceptions
so callers can handle failure categories programmatically.

Hierarchy::

    PlatformException
    ├── AdapterException
    │   ├── AdapterNotAvailableException
    │   ├── AdapterInitializationException
    │   └── AdapterOperationException
    ├── LocatorException
    │   ├── ElementNotFoundException
    │   ├── LocatorResolutionException
    │   └── AmbiguousLocatorException
    ├── SessionException
    │   ├── SessionNotActiveException
    │   └── SessionInitializationException
    ├── ApplicationException
    │   ├── ApplicationLaunchException
    │   ├── ApplicationNotFoundException
    │   └── ApplicationCrashException
    ├── ConfigurationException
    │   ├── InvalidConfigException
    │   └── MissingConfigException
    └── RecoveryException
        ├── MaxRetriesExceededException
        └── RecoveryFailedException
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------


class PlatformException(Exception):
    """Base exception for all Desktop Automation Platform errors."""

    def __init__(self, message: str, metadata: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.metadata: dict[str, Any] = metadata or {}

    def __repr__(self) -> str:
        return f"{type(self).__name__}(message={self.message!r}, metadata={self.metadata})"


# ---------------------------------------------------------------------------
# Adapter exceptions
# ---------------------------------------------------------------------------


class AdapterException(PlatformException):
    """Base for all adapter-layer failures."""

    def __init__(
        self,
        message: str,
        adapter_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, metadata)
        self.adapter_type = adapter_type


class AdapterNotAvailableException(AdapterException):
    """
    Raised when an adapter's required native dependencies are not installed
    or the runtime environment does not support the adapter.
    """

    def __init__(self, adapter_type: str, reason: str) -> None:
        super().__init__(
            message=f"Adapter '{adapter_type}' is not available: {reason}",
            adapter_type=adapter_type,
            metadata={"reason": reason},
        )


class AdapterInitializationException(AdapterException):
    """Raised when an adapter fails to initialise its native connection."""

    def __init__(
        self,
        adapter_type: str,
        reason: str,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(
            message=f"Adapter '{adapter_type}' failed to initialise: {reason}",
            adapter_type=adapter_type,
            metadata={"reason": reason, "original_error": str(original_error)},
        )
        self.original_error = original_error


class AdapterOperationException(AdapterException):
    """Raised when a specific automation action fails at the adapter level."""

    def __init__(
        self,
        action: str,
        message: str,
        adapter_type: str | None = None,
        screenshot_path: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        combined = metadata or {}
        combined["action"] = action
        if screenshot_path:
            combined["screenshot_path"] = screenshot_path
        super().__init__(
            message=f"Action '{action}' failed: {message}",
            adapter_type=adapter_type,
            metadata=combined,
        )
        self.action = action
        self.screenshot_path = screenshot_path


# ---------------------------------------------------------------------------
# Locator exceptions
# ---------------------------------------------------------------------------


class LocatorException(PlatformException):
    """Base for all locator-resolution failures."""

    def __init__(
        self,
        message: str,
        locator_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, metadata)
        self.locator_name = locator_name


class ElementNotFoundException(LocatorException):
    """
    Raised when no UI element matches any strategy in the locator chain
    within the configured timeout.
    """

    def __init__(
        self,
        locator_name: str,
        strategies_tried: list[str],
        timeout_seconds: float,
    ) -> None:
        super().__init__(
            message=(
                f"Element '{locator_name}' not found after trying "
                f"{len(strategies_tried)} strategy/strategies "
                f"(timeout={timeout_seconds}s): {strategies_tried}"
            ),
            locator_name=locator_name,
            metadata={
                "strategies_tried": strategies_tried,
                "timeout_seconds": timeout_seconds,
            },
        )
        self.strategies_tried = strategies_tried
        self.timeout_seconds = timeout_seconds


class LocatorResolutionException(LocatorException):
    """Raised when the locator engine cannot translate a strategy to native syntax."""

    def __init__(self, locator_name: str, strategy: str, adapter_type: str) -> None:
        super().__init__(
            message=(
                f"Adapter '{adapter_type}' cannot resolve strategy "
                f"'{strategy}' for locator '{locator_name}'"
            ),
            locator_name=locator_name,
            metadata={"strategy": strategy, "adapter_type": adapter_type},
        )


class AmbiguousLocatorException(LocatorException):
    """Raised when a locator matches more elements than expected."""

    def __init__(self, locator_name: str, match_count: int) -> None:
        super().__init__(
            message=f"Locator '{locator_name}' matched {match_count} elements (expected 1)",
            locator_name=locator_name,
            metadata={"match_count": match_count},
        )


# ---------------------------------------------------------------------------
# Session exceptions
# ---------------------------------------------------------------------------


class SessionException(PlatformException):
    """Base for session-lifecycle failures."""

    def __init__(
        self,
        message: str,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, metadata)
        self.session_id = session_id


class SessionNotActiveException(SessionException):
    """Raised when an operation is attempted on a non-active session."""

    def __init__(self, session_id: str, current_state: str) -> None:
        super().__init__(
            message=f"Session '{session_id}' is not active (state={current_state})",
            session_id=session_id,
            metadata={"current_state": current_state},
        )


class SessionInitializationException(SessionException):
    """Raised when a session cannot be established."""

    def __init__(self, reason: str, original_error: Exception | None = None) -> None:
        super().__init__(
            message=f"Session initialization failed: {reason}",
            metadata={
                "reason": reason,
                "original_error": str(original_error) if original_error else None,
            },
        )
        self.original_error = original_error


# ---------------------------------------------------------------------------
# Application exceptions
# ---------------------------------------------------------------------------


class ApplicationException(PlatformException):
    """Base for application-lifecycle failures."""

    def __init__(
        self,
        message: str,
        app_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, metadata)
        self.app_name = app_name


class ApplicationLaunchException(ApplicationException):
    """Raised when the target application cannot be launched."""

    def __init__(
        self,
        app_name: str,
        executable: str,
        reason: str,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(
            message=f"Failed to launch '{app_name}' ({executable}): {reason}",
            app_name=app_name,
            metadata={
                "executable": executable,
                "reason": reason,
                "original_error": str(original_error) if original_error else None,
            },
        )


class ApplicationNotFoundException(ApplicationException):
    """Raised when the target application process cannot be found."""

    def __init__(self, identifier: str | int) -> None:
        super().__init__(
            message=f"Application not found: {identifier!r}",
            metadata={"identifier": str(identifier)},
        )


class ApplicationCrashException(ApplicationException):
    """Raised when the application process terminates unexpectedly during automation."""

    def __init__(self, app_name: str, exit_code: int | None = None) -> None:
        super().__init__(
            message=f"Application '{app_name}' crashed (exit_code={exit_code})",
            app_name=app_name,
            metadata={"exit_code": exit_code},
        )


# ---------------------------------------------------------------------------
# Configuration exceptions
# ---------------------------------------------------------------------------


class ConfigurationException(PlatformException):
    """Base for configuration-layer failures."""


class InvalidConfigException(ConfigurationException):
    """Raised when a loaded configuration fails schema validation."""

    def __init__(self, path: str, validation_errors: list[str]) -> None:
        super().__init__(
            message=f"Invalid configuration at '{path}': {'; '.join(validation_errors)}",
            metadata={"path": path, "validation_errors": validation_errors},
        )
        self.path = path
        self.validation_errors = validation_errors


class MissingConfigException(ConfigurationException):
    """Raised when a required configuration file cannot be found."""

    def __init__(self, path: str) -> None:
        super().__init__(
            message=f"Configuration file not found: '{path}'",
            metadata={"path": path},
        )


# ---------------------------------------------------------------------------
# Recovery exceptions
# ---------------------------------------------------------------------------


class RecoveryException(PlatformException):
    """Base for recovery-engine failures."""


class MaxRetriesExceededException(RecoveryException):
    """Raised when all retry attempts for an action have been exhausted."""

    def __init__(self, action: str, max_retries: int, last_error: str) -> None:
        super().__init__(
            message=(
                f"Action '{action}' failed after {max_retries} retries. "
                f"Last error: {last_error}"
            ),
            metadata={
                "action": action,
                "max_retries": max_retries,
                "last_error": last_error,
            },
        )
        self.action = action
        self.max_retries = max_retries


class RecoveryFailedException(RecoveryException):
    """Raised when all recovery strategies fail to restore the session."""

    def __init__(self, strategies_tried: list[str], root_error: str) -> None:
        super().__init__(
            message=f"All recovery strategies failed: {strategies_tried}. Root: {root_error}",
            metadata={"strategies_tried": strategies_tried, "root_error": root_error},
        )
