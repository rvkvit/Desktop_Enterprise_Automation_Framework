"""
FlaUI adapter package — primary desktop automation engine.

FlaUI wraps Microsoft UI Automation (UIA2 / UIA3) via .NET.
Requires: pythonnet (clr), FlaUI.Core.dll, FlaUI.UIA3.dll

Install FlaUI assemblies:
    # Via NuGet (recommended):
    nuget install FlaUI.UIA3 -OutputDirectory lib/flaui

    # Or via the flaui Python package (thin wrapper, not used here):
    pip install flaui

This adapter uses pythonnet directly for maximum control and compatibility.
"""
