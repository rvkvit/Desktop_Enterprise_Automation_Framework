"""
PlatformContainer — dependency injection container for the Desktop Automation Platform.

Built on ``dependency_injector`` (DeclarativeContainer pattern).

Container topology
------------------
The container wires together the entire platform. All bindings are Singleton
by default (one instance per container) except where Factories are used for
per-session objects.

Usage — typical test script::

    from desktop_automation_platform.core.container import PlatformContainer

    container = PlatformContainer()
    container.config.from_yaml("config/claims.yaml")
    container.wire(modules=["desktop_automation_platform.robot_keywords.desktop_keywords"])

Usage — programmatic::

    container = PlatformContainer()
    container.bootstrap(config_path="config/claims.yaml")
    manager = container.adapter_manager()

Wiring enables @inject decorators in keyword modules to receive their
dependencies automatically without explicit constructor calls.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from dependency_injector import containers, providers

from desktop_automation_platform.adapters.adapter_manager import AdapterManager
from desktop_automation_platform.adapters.adapter_registry import AdapterRegistry
from desktop_automation_platform.adapters.detector.application_detector import (
    WindowsApplicationDetector,
)
from desktop_automation_platform.adapters.detector.process_inspector import ProcessInspector
from desktop_automation_platform.adapters.detector.technology_classifier import (
    TechnologyClassifier,
)
from desktop_automation_platform.config.framework_config import YamlConfigManager
from desktop_automation_platform.config.yaml_loader import YamlConfigLoader
from desktop_automation_platform.utils.logger import configure_logging, get_logger

if TYPE_CHECKING:
    from desktop_automation_platform.config.schema import PlatformConfig

_log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Concrete ScreenshotManager (stub — full implementation in Phase 3)
# ---------------------------------------------------------------------------


class _DefaultScreenshotManager:
    """
    Minimal screenshot manager used until the full implementation is injected.
    Captures via PIL if available, otherwise creates an empty placeholder.
    """

    def __init__(self, output_dir: str = "reports/screenshots") -> None:
        self._output_dir = Path(output_dir)

    def capture(self, session: object, label: str | None = None, subfolder: str | None = None) -> str:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime

        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        name = f"{label or 'screenshot'}_{ts}.png"
        out = self._output_dir / (subfolder or "") / name
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            import PIL.ImageGrab  # type: ignore[import]

            img = PIL.ImageGrab.grab()
            img.save(str(out))
        except Exception:
            out.touch()
        return str(out)

    def capture_on_failure(
        self, session: object, action_name: str, test_name: str | None = None
    ) -> str | None:
        try:
            return self.capture(session, label=f"FAILURE_{action_name}", subfolder="failures")
        except Exception:
            return None

    def capture_element(
        self, session: object, bounding_rect: dict[str, int], label: str | None = None
    ) -> str:
        return self.capture(session, label=label, subfolder="elements")

    def get_screenshot_directory(self) -> str:
        return str(self._output_dir)

    def set_screenshot_directory(self, directory: str) -> None:
        self._output_dir = Path(directory)

    def purge_old_screenshots(self, max_age_days: int) -> int:
        import time

        cutoff = time.time() - max_age_days * 86400
        deleted = 0
        if self._output_dir.exists():
            for f in self._output_dir.rglob("*.png"):
                if f.stat().st_mtime < cutoff:
                    f.unlink(missing_ok=True)
                    deleted += 1
        return deleted


# ---------------------------------------------------------------------------
# DI Container
# ---------------------------------------------------------------------------


class PlatformContainer(containers.DeclarativeContainer):
    """
    Declarative DI container for the Desktop Automation Platform.

    All providers are Singletons within the container scope — a single
    container instance per test run is the expected usage model.
    """

    # ------------------------------------------------------------------
    # Configuration providers
    # ------------------------------------------------------------------

    wiring_config = containers.WiringConfiguration(
        packages=["desktop_automation_platform"],
    )

    # Raw YAML loader (stateless, no config needed)
    yaml_loader: providers.Provider[YamlConfigLoader] = providers.Singleton(YamlConfigLoader)

    # Config manager wrapping the loader
    config_manager: providers.Provider[YamlConfigManager] = providers.Singleton(
        YamlConfigManager,
        loader=yaml_loader,
    )

    # ------------------------------------------------------------------
    # Process inspection / technology detection
    # ------------------------------------------------------------------

    process_inspector: providers.Provider[ProcessInspector] = providers.Singleton(
        ProcessInspector
    )

    technology_classifier: providers.Provider[TechnologyClassifier] = providers.Singleton(
        TechnologyClassifier
    )

    application_detector: providers.Provider[WindowsApplicationDetector] = providers.Singleton(
        WindowsApplicationDetector,
        inspector=process_inspector,
        classifier=technology_classifier,
    )

    # ------------------------------------------------------------------
    # Adapter layer
    # ------------------------------------------------------------------

    adapter_registry: providers.Provider[AdapterRegistry] = providers.Singleton(AdapterRegistry)

    # ------------------------------------------------------------------
    # Screenshot manager (replaced in Phase 3 with full implementation)
    # ------------------------------------------------------------------

    screenshot_manager: providers.Provider[_DefaultScreenshotManager] = providers.Singleton(
        _DefaultScreenshotManager,
    )

    # ------------------------------------------------------------------
    # Adapter manager (requires config — wired after bootstrap)
    # ------------------------------------------------------------------

    # adapter_manager is built dynamically in bootstrap() because it needs
    # the loaded PlatformConfig, which is not available at container
    # definition time (config path is unknown until bootstrap is called).

    # ------------------------------------------------------------------
    # Bootstrap entry point
    # ------------------------------------------------------------------


def bootstrap(
    config_path: str | Path,
    *,
    register_default_adapters: bool = True,
) -> tuple[PlatformContainer, AdapterManager]:
    """
    Initialise the full platform from a YAML config file.

    Returns the populated container and a ready-to-use AdapterManager.

    Call once at the start of a test session::

        container, manager = bootstrap("config/claims.yaml")

    Parameters
    ----------
    config_path:
        Path to the YAML platform configuration file.
    register_default_adapters:
        If True, attempt to register all built-in adapters that are
        available in the current environment.
    """
    container = PlatformContainer()

    # Load and validate configuration
    cfg_manager: YamlConfigManager = container.config_manager()
    platform_config: PlatformConfig = cfg_manager.load(config_path)

    # Initialise logging based on config
    configure_logging(
        level=platform_config.framework.logging_level.value,
        structured=platform_config.framework.structured_logging,
    )

    _log.info(
        "platform_bootstrap_started",
        config_path=str(config_path),
        adapter_mode=platform_config.framework.adapter_mode.value,
        app_name=platform_config.application.name,
    )

    # Configure screenshot manager output directory
    screenshot_manager = container.screenshot_manager()
    screenshot_manager.set_screenshot_directory(
        platform_config.reporting.screenshots_directory
    )

    # Build adapter manager
    registry: AdapterRegistry = container.adapter_registry()
    detector: WindowsApplicationDetector = container.application_detector()

    if register_default_adapters:
        _register_available_adapters(registry, platform_config, screenshot_manager)

    adapter_manager = AdapterManager(
        registry=registry,
        detector=detector,
        config=platform_config,
    )

    _log.info(
        "platform_bootstrap_complete",
        available_adapters=[r.adapter_type.value for r in registry.all_available()],
    )

    return container, adapter_manager


def _register_available_adapters(
    registry: AdapterRegistry,
    config: "PlatformConfig",
    screenshot_manager: _DefaultScreenshotManager,
) -> None:
    """
    Attempt to register each built-in adapter.
    Failures are logged as warnings — a missing adapter library must not
    prevent the platform from starting if that adapter is not needed.
    """
    from desktop_automation_platform.core.models import ApplicationTechnology

    adapter_specs = [
        # (module_path, class_name, AdapterType, supported_technologies)
        (
            "desktop_automation_platform.adapters.flaui.adapter",
            "FlaUIAdapter",
            "flaui",
            [
                ApplicationTechnology.WPF,
                ApplicationTechnology.WINFORMS,
                ApplicationTechnology.WINUI3,
                ApplicationTechnology.MAUI,
                ApplicationTechnology.WIN32,
                ApplicationTechnology.PACKAGED,
            ],
        ),
        (
            "desktop_automation_platform.adapters.pywinauto.adapter",
            "PywinautoAdapter",
            "pywinauto",
            [
                ApplicationTechnology.WIN32,
                ApplicationTechnology.WPF,
                ApplicationTechnology.WINFORMS,
                ApplicationTechnology.QT,
            ],
        ),
        (
            "desktop_automation_platform.adapters.winappdriver.adapter",
            "WinAppDriverAdapter",
            "winappdriver",
            [
                ApplicationTechnology.WPF,
                ApplicationTechnology.WINFORMS,
                ApplicationTechnology.WIN32,
                ApplicationTechnology.PACKAGED,
            ],
        ),
        (
            "desktop_automation_platform.adapters.java_access_bridge.adapter",
            "JavaAccessBridgeAdapter",
            "java_access_bridge",
            [ApplicationTechnology.JAVA_SWING, ApplicationTechnology.JAVA_AWT],
        ),
        (
            "desktop_automation_platform.adapters.electron_playwright.adapter",
            "ElectronPlaywrightAdapter",
            "electron_playwright",
            [ApplicationTechnology.ELECTRON],
        ),
        (
            "desktop_automation_platform.adapters.sikuli_image.adapter",
            "SikuliImageAdapter",
            "sikuli_image",
            [ApplicationTechnology.CITRIX, ApplicationTechnology.RDP],
        ),
        (
            "desktop_automation_platform.adapters.autoit.adapter",
            "AutoItAdapter",
            "autoit",
            [ApplicationTechnology.WIN32],
        ),
    ]

    for module_path, class_name, adapter_type_str, technologies in adapter_specs:
        _try_register_adapter(
            registry=registry,
            module_path=module_path,
            class_name=class_name,
            adapter_type_str=adapter_type_str,
            technologies=technologies,
            config=config,
            screenshot_manager=screenshot_manager,
        )


def _try_register_adapter(
    registry: AdapterRegistry,
    module_path: str,
    class_name: str,
    adapter_type_str: str,
    technologies: list,
    config: "PlatformConfig",
    screenshot_manager: _DefaultScreenshotManager,
) -> None:
    """Import the adapter module and register it, logging any import errors."""
    import importlib

    from desktop_automation_platform.core.models import AdapterType

    adapter_type = AdapterType(adapter_type_str)

    try:
        module = importlib.import_module(module_path)
        adapter_class = getattr(module, class_name)

        def factory(cls=adapter_class, cfg=config, ss=screenshot_manager):
            return cls(config=cfg, screenshot_manager=ss)

        # Defer availability checks to launch time so all importable adapters
        # appear in the registry and give clear errors when actually used.
        registry.register(
            adapter_type=adapter_type,
            factory=factory,
            supported_technologies=technologies,
            check_availability=False,
        )
    except ImportError as exc:
        _log.warning(
            "adapter_import_failed",
            adapter=adapter_type_str,
            reason=str(exc),
            note="Install the adapter's optional dependencies to enable it.",
        )
    except Exception as exc:
        _log.warning(
            "adapter_registration_failed",
            adapter=adapter_type_str,
            error=str(exc),
        )
