"""
FlaUIAutomationFactory — bootstraps the pythonnet / FlaUI .NET interop layer.

Responsibilities
----------------
1. Locate FlaUI assemblies on disk (several search strategies)
2. Add assembly paths to the CLR search path
3. Import FlaUI namespaces via ``clr.AddReference``
4. Construct and return a ``UIA2Automation`` or ``UIA3Automation`` instance

Assembly search order
---------------------
1. ``FLAUI_PATH`` environment variable (explicit override)
2. Project-local ``lib/flaui/`` directory
3. NuGet global packages cache (``%USERPROFILE%\\.nuget\\packages``)
4. ``C:\\Program Files\\FlaUI``

Design: the factory is called once per adapter instance and caches the
result.  Subsequent calls return the same automation object.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from desktop_automation_platform.core.exceptions import AdapterInitializationException
from desktop_automation_platform.utils.logger import get_logger

_log = get_logger(__name__)

# Cached automation singleton — one per Python process is sufficient
_automation_cache: dict[str, Any] = {}

# FlaUI assembly names required for UIA3 (order matters — deps before FlaUI)
_REQUIRED_ASSEMBLIES = [
    "System.Drawing.Common",       # GDI+ interop; FlaUI.Core refs version 4.x of this
    "Interop.UIAutomationClient",  # COM interop layer; must load before FlaUI.UIA3
    "System.Management",           # WMI interop required by FlaUI on .NET Core
    "FlaUI.Core",
    "FlaUI.UIA3",
]
_UIA2_ASSEMBLY = "FlaUI.UIA2"

# NuGet package IDs → subfolder patterns
_NUGET_PACKAGES = {
    "FlaUI.Core": "flaui.core",
    "FlaUI.UIA3": "flaui.uia3",
    "FlaUI.UIA2": "flaui.uia2",
}


def _find_flaui_assembly_dirs() -> list[Path]:
    """Return candidate directories that may contain FlaUI DLLs."""
    candidates: list[Path] = []

    # 1. Explicit env override
    env_path = os.environ.get("FLAUI_PATH")
    if env_path:
        candidates.append(Path(env_path))

    # 2. Project-local lib/flaui
    project_root = Path(__file__).resolve().parents[3]
    candidates.append(project_root / "lib" / "flaui")

    # 3. NuGet global cache
    nuget_root = Path.home() / ".nuget" / "packages"
    if nuget_root.exists():
        for pkg_id, folder in _NUGET_PACKAGES.items():
            pkg_dir = nuget_root / folder
            if pkg_dir.exists():
                # Find the latest version sub-directory
                versions = sorted(pkg_dir.iterdir(), reverse=True)
                for ver_dir in versions:
                    net_dirs = list(ver_dir.glob("lib/net*"))
                    if net_dirs:
                        candidates.append(sorted(net_dirs)[-1])
                        break

    # 4. Well-known install paths
    candidates.append(Path("C:/Program Files/FlaUI"))
    candidates.append(Path("C:/FlaUI"))

    return [d for d in candidates if d.exists()]


def _find_dll(assembly_name: str, search_dirs: list[Path]) -> Path | None:
    """
    Locate a specific DLL file by searching candidate directories.
    Returns the first match, or None if not found.
    """
    filename = f"{assembly_name}.dll"
    for directory in search_dirs:
        candidate = directory / filename
        if candidate.exists():
            return candidate
    return None


def _load_flaui_clr(automation_type: str) -> None:
    """
    Load FlaUI assemblies into the CLR. Idempotent.

    FlaUI 4.x targets .NET 6+, so pythonnet must use the coreclr runtime (not
    the .NET Framework netfx runtime that pythonnet picks by default on Windows).
    We configure this before the first ``import clr``.
    """
    # Must configure runtime before the first 'import clr' in this process.
    # FlaUI 4.x needs Microsoft.WindowsDesktop.App (for System.Drawing.Common
    # and its GDI+ internals), not just NETCore.App which pythonnet loads by default.
    # We pass a runtimeconfig.json that declares the WindowsDesktop framework so the
    # CLR picks it up via its normal framework resolution / roll-forward mechanism.
    if "clr" not in sys.modules:
        assembly_dirs = _find_flaui_assembly_dirs()
        runtimeconfig: Path | None = None
        for d in assembly_dirs:
            candidate = d / "flaui.runtimeconfig.json"
            if candidate.exists():
                runtimeconfig = candidate
                break

        try:
            import clr_loader  # type: ignore[import]
            from pythonnet import set_runtime  # type: ignore[import]

            if runtimeconfig is not None:
                rt = clr_loader.get_coreclr(runtime_config=str(runtimeconfig))
            else:
                rt = clr_loader.get_coreclr()
            set_runtime(rt)
        except RuntimeError:
            pass  # runtime already loaded — proceed with whatever is active
        except (ImportError, AttributeError):
            # Fallback: older pythonnet.load() API
            try:
                import pythonnet as _pn  # type: ignore[import]
                _pn.load("coreclr")
            except Exception:
                pass

    try:
        import clr  # type: ignore[import]
    except ImportError as exc:
        raise AdapterInitializationException(
            adapter_type="flaui",
            reason=(
                "pythonnet (clr) is not installed. "
                "Install it with: pip install pythonnet"
            ),
            original_error=exc,
        ) from exc

    assembly_dirs = _find_flaui_assembly_dirs()

    assemblies = list(_REQUIRED_ASSEMBLIES)
    if automation_type.upper() == "UIA2":
        assemblies = ["System.Drawing.Common", "Interop.UIAutomationClient", "System.Management", "FlaUI.Core", _UIA2_ASSEMBLY]

    missing: list[str] = []
    for asm_name in assemblies:
        # Try by full path first (required for pythonnet 3.x / .NET Core)
        dll_path = _find_dll(asm_name, assembly_dirs)
        try:
            if dll_path is not None:
                clr.AddReference(str(dll_path))
            else:
                # Fallback: bare name (works on Mono / GAC-registered assemblies)
                clr.AddReference(asm_name)
            _log.debug("flaui_assembly_loaded", assembly=asm_name, path=str(dll_path or "by-name"))
        except Exception as exc:
            _log.debug("flaui_assembly_load_failed", assembly=asm_name, error=str(exc))
            missing.append(asm_name)

    if missing:
        search_dirs_str = [str(d) for d in assembly_dirs] or ["(none found)"]
        raise AdapterInitializationException(
            adapter_type="flaui",
            reason=(
                f"FlaUI assemblies not found: {missing}. "
                f"Searched: {search_dirs_str}. "
                "Run .\\scripts\\setup_flaui.ps1 to download them, or "
                "set the FLAUI_PATH environment variable to their directory."
            ),
        )


def create_automation(automation_type: str = "UIA3") -> Any:
    """
    Create (or return cached) a FlaUI automation instance.

    Parameters
    ----------
    automation_type:
        "UIA3" (default, recommended for WPF/WinUI3/modern apps)
        "UIA2" (legacy — Windows 7, older accessibility trees)

    Returns a ``UIA3Automation`` or ``UIA2Automation`` instance.
    """
    cache_key = automation_type.upper()
    if cache_key in _automation_cache:
        return _automation_cache[cache_key]

    _load_flaui_clr(automation_type)

    try:
        if cache_key == "UIA3":
            from FlaUI.UIA3 import UIA3Automation  # type: ignore[import]

            automation = UIA3Automation()
        else:
            from FlaUI.UIA2 import UIA2Automation  # type: ignore[import]

            automation = UIA2Automation()
    except Exception as exc:
        raise AdapterInitializationException(
            adapter_type="flaui",
            reason=f"Failed to create {automation_type} automation: {exc}",
            original_error=exc,
        ) from exc

    _automation_cache[cache_key] = automation
    _log.info("flaui_automation_created", type=automation_type)
    return automation


def is_flaui_available() -> bool:
    """
    Return True if pythonnet and FlaUI assemblies are resolvable.
    Never raises — used by is_available() in the adapter.
    """
    try:
        create_automation("UIA3")
        return True
    except Exception as exc:
        _log.debug("flaui_availability_check_failed", error=str(exc))
        return False
