"""
Windows process inspection utilities.

Provides low-level helpers for process enumeration, module listing,
window class name retrieval, and executable PE metadata reading.
All functions fail gracefully and return None / empty collections rather
than raising, making them safe to call from the detector heuristics.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path
from typing import Any

import psutil

from desktop_automation_platform.utils.logger import get_logger

_log = get_logger(__name__)

_IS_WINDOWS = sys.platform == "win32"


# ---------------------------------------------------------------------------
# Process information
# ---------------------------------------------------------------------------


def get_process_info(pid: int) -> dict[str, Any] | None:
    """
    Return a dict of process metadata for ``pid``, or None if not found.

    Keys: name, exe, cmdline, cwd, create_time, status, memory_rss_mb
    """
    try:
        proc = psutil.Process(pid)
        with proc.oneshot():
            return {
                "name": proc.name(),
                "exe": proc.exe(),
                "cmdline": proc.cmdline(),
                "cwd": proc.cwd(),
                "create_time": proc.create_time(),
                "status": proc.status(),
                "memory_rss_mb": proc.memory_info().rss / (1024 * 1024),
            }
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
        return None


def get_process_modules(pid: int) -> list[str]:
    """
    Return the list of loaded DLL/SO names for ``pid`` (lowercase, basename only).

    Returns empty list if the process is inaccessible (e.g. elevated).
    """
    if not _IS_WINDOWS:
        return []
    try:
        import win32api  # type: ignore[import]
        import win32con  # type: ignore[import]
        import win32process  # type: ignore[import]

        handle = win32api.OpenProcess(
            win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
            False,
            pid,
        )
        try:
            modules = win32process.EnumProcessModules(handle)
            names: list[str] = []
            for mod in modules:
                try:
                    name = win32api.GetModuleFileNameEx(handle, mod)
                    names.append(Path(name).name.lower())
                except Exception:
                    continue
            return names
        finally:
            win32api.CloseHandle(handle)
    except Exception as exc:
        _log.debug("get_process_modules_failed", pid=pid, error=str(exc))
        return []


def find_pids_by_executable(executable_name: str) -> list[int]:
    """
    Return all PIDs whose executable filename matches ``executable_name``
    (case-insensitive, basename comparison).
    """
    target = executable_name.lower()
    pids: list[int] = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() == target:
                pids.append(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return pids


def find_pids_by_window_title(title: str, partial: bool = True) -> list[int]:
    """
    Return PIDs of all processes with a top-level window matching ``title``.

    Only available on Windows; returns empty list elsewhere.
    """
    if not _IS_WINDOWS:
        return []
    try:
        import win32gui  # type: ignore[import]
        import win32process  # type: ignore[import]

        pids: list[int] = []
        title_lower = title.lower()

        def _callback(hwnd: int, _: Any) -> bool:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            window_title = win32gui.GetWindowText(hwnd)
            match = (
                title_lower in window_title.lower()
                if partial
                else window_title.lower() == title_lower
            )
            if match:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid not in pids:
                    pids.append(pid)
            return True

        win32gui.EnumWindows(_callback, None)
        return pids
    except Exception as exc:
        _log.debug("find_pids_by_window_title_failed", title=title, error=str(exc))
        return []


# ---------------------------------------------------------------------------
# Window class name inspection
# ---------------------------------------------------------------------------


def get_window_class_names(pid: int) -> list[str]:
    """
    Return unique window class names for all top-level windows belonging to ``pid``.

    Only available on Windows; returns empty list elsewhere.
    """
    if not _IS_WINDOWS:
        return []
    try:
        import win32gui  # type: ignore[import]
        import win32process  # type: ignore[import]

        class_names: list[str] = []

        def _callback(hwnd: int, _: Any) -> bool:
            try:
                _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
                if window_pid == pid:
                    cls = win32gui.GetClassName(hwnd)
                    if cls and cls not in class_names:
                        class_names.append(cls)
            except Exception:
                pass
            return True

        win32gui.EnumWindows(_callback, None)
        return class_names
    except Exception as exc:
        _log.debug("get_window_class_names_failed", pid=pid, error=str(exc))
        return []


# ---------------------------------------------------------------------------
# Executable PE metadata
# ---------------------------------------------------------------------------


def read_pe_assembly_name(executable_path: str) -> str | None:
    """
    Attempt to read the .NET assembly name from a PE file's CLI header.

    Returns None if the file is not a .NET assembly or cannot be parsed.
    This is a lightweight heuristic check — not a full PE parser.
    """
    path = Path(executable_path)
    if not path.exists():
        return None
    try:
        data = path.read_bytes()
        # MZ header check
        if data[:2] != b"MZ":
            return None
        # Check for CLI header signature at a fixed offset (simplified heuristic)
        # Full implementation would parse the PE optional header COM descriptor RVA
        if b"mscoree.dll" in data[:4096] or b"MSCOREE.DLL" in data[:4096]:
            return path.stem
        return None
    except OSError:
        return None


def is_dotnet_executable(executable_path: str) -> bool:
    """Return True if the executable appears to be a .NET assembly."""
    return read_pe_assembly_name(executable_path) is not None


def is_process_alive(pid: int) -> bool:
    """Return True if a process with ``pid`` exists and is not zombie/dead."""
    try:
        proc = psutil.Process(pid)
        return proc.status() not in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False
