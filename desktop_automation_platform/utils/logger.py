"""
Structured logging factory for the Desktop Automation Platform.

Uses ``structlog`` to produce machine-parseable JSON log records in CI/CD
environments and human-readable coloured output in development terminals.

All platform modules obtain a logger via::

    from desktop_automation_platform.utils.logger import get_logger
    _log = get_logger(__name__)
    _log.info("action_started", action="click", locator="LOGIN_BUTTON")

Log schema
----------
Every record includes:
    timestamp   ISO-8601 UTC
    level       DEBUG / INFO / WARNING / ERROR / CRITICAL
    logger      module path of the emitter
    event       human description of what happened
    + arbitrary key=value context pairs
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor


# ---------------------------------------------------------------------------
# Processors
# ---------------------------------------------------------------------------


def _add_log_level(
    logger: Any,  # noqa: ANN401
    method: str,
    event_dict: EventDict,
) -> EventDict:
    """Inject a normalised 'level' key for downstream log parsers."""
    event_dict["level"] = method.upper()
    return event_dict


def _drop_color_message(
    logger: Any,  # noqa: ANN401
    method: str,
    event_dict: EventDict,
) -> EventDict:
    """Remove structlog's internal _record colour helper if present."""
    event_dict.pop("_record", None)
    event_dict.pop("_from_structlog", None)
    return event_dict


# ---------------------------------------------------------------------------
# Public configuration function
# ---------------------------------------------------------------------------


def configure_logging(
    level: str = "INFO",
    structured: bool = True,
    force: bool = False,
) -> None:
    """
    Configure the global structlog / stdlib logging pipeline.

    Call once at process startup (PlatformContainer.bootstrap() does this).
    Subsequent calls are no-ops unless ``force=True``.

    Parameters
    ----------
    level:
        Minimum log level string (DEBUG / INFO / WARNING / ERROR / CRITICAL).
    structured:
        True → JSON output (CI/CD).  False → human-readable coloured output.
    force:
        Re-configure even if already configured (useful in tests).
    """
    if structlog.is_configured() and not force:
        return

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        _add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        _drop_color_message,
    ]

    if structured:
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    # Remove default handlers to avoid duplicate output
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Suppress noisy third-party loggers
    for noisy in ("comtypes", "pywinauto", "PIL", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Return a structlog BoundLogger bound to ``name``.

    Usage::
        _log = get_logger(__name__)
        _log.info("session_opened", session_id=session.session_id)
    """
    return structlog.get_logger(name)


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------


def bind_test_context(test_name: str, suite_name: str | None = None) -> None:
    """
    Bind test metadata into the structlog context vars so every subsequent
    log record in this thread is annotated automatically.

    Call at the start of each Robot Framework test case.
    """
    ctx: dict[str, str] = {"test_name": test_name}
    if suite_name:
        ctx["suite_name"] = suite_name
    structlog.contextvars.bind_contextvars(**ctx)


def bind_session_context(session_id: str, adapter_type: str) -> None:
    """Bind session metadata into the structlog context vars."""
    structlog.contextvars.bind_contextvars(
        session_id=session_id,
        adapter_type=adapter_type,
    )


def clear_log_context() -> None:
    """Clear all bound context vars (call at test teardown)."""
    structlog.contextvars.clear_contextvars()
