"""
TechnologyClassifier — heuristic engine for desktop technology classification.

Each ``ClassifierRule`` is a self-contained evidence probe that inspects
process signals and returns a confidence contribution. Rules are additive:
the classifier runs all rules and sums the weighted confidence scores for
each technology candidate.

Architecture rationale
----------------------
Rules are declared as data (lists of ``ClassifierRule`` instances) rather
than method switches so that:
  1. New rules can be added without modifying existing logic
  2. Each rule can be unit-tested in isolation
  3. Confidence weighting is explicit and auditable

Signal taxonomy
---------------
MODULE    — DLL/SO name present in the process module list
CLASS     — Win32 window class name prefix/suffix/exact match
EXE_NAME  — Executable filename pattern
PE_META   — PE file metadata (mscoree.dll import, manifest, etc.)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from desktop_automation_platform.core.models import AdapterType, ApplicationTechnology, DetectionResult


# ---------------------------------------------------------------------------
# Rule model
# ---------------------------------------------------------------------------


@dataclass
class ClassifierRule:
    """
    A single evidence probe for one technology.

    ``probe`` receives the ``ProcessSignals`` snapshot and returns a
    confidence contribution (0.0–1.0).  Zero means no evidence found.
    """

    technology: ApplicationTechnology
    name: str
    weight: float  # Contribution to confidence when probe matches (0.0–1.0)
    probe: Callable[["ProcessSignals"], bool]
    description: str = ""


@dataclass
class ProcessSignals:
    """
    Normalised, lowercased signals collected from a process before classification.
    All string lists contain lowercased values for case-insensitive matching.
    """

    pid: int
    exe_name: str                        # e.g. "claims.exe"
    modules: list[str]                   # lowercased DLL names
    window_class_names: list[str]        # Win32 class names (original case)
    cmdline: list[str]                   # process command-line tokens
    is_dotnet: bool = False              # PE contains mscoree import

    def has_module(self, *module_names: str) -> bool:
        """Return True if any of the given module names appears in the module list."""
        return any(m.lower() in self.modules for m in module_names)

    def has_window_class_prefix(self, *prefixes: str) -> bool:
        """Return True if any window class starts with one of the given prefixes."""
        for cls in self.window_class_names:
            for prefix in prefixes:
                if cls.lower().startswith(prefix.lower()):
                    return True
        return False

    def has_window_class_containing(self, *substrings: str) -> bool:
        for cls in self.window_class_names:
            for sub in substrings:
                if sub.lower() in cls.lower():
                    return True
        return False

    def exe_matches(self, *patterns: str) -> bool:
        """Return True if the exe name matches any of the glob-style patterns."""
        for p in patterns:
            if re.fullmatch(p.lower().replace("*", ".*"), self.exe_name.lower()):
                return True
        return False


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

#
# Technology → recommended adapter mapping
#
_TECHNOLOGY_ADAPTER_MAP: dict[ApplicationTechnology, AdapterType] = {
    ApplicationTechnology.WPF: AdapterType.FLAUI,
    ApplicationTechnology.WINFORMS: AdapterType.FLAUI,
    ApplicationTechnology.WINUI3: AdapterType.FLAUI,
    ApplicationTechnology.MAUI: AdapterType.FLAUI,
    ApplicationTechnology.WIN32: AdapterType.PYWINAUTO,
    ApplicationTechnology.JAVA_SWING: AdapterType.JAVA_ACCESS_BRIDGE,
    ApplicationTechnology.JAVA_AWT: AdapterType.JAVA_ACCESS_BRIDGE,
    ApplicationTechnology.QT: AdapterType.PYWINAUTO,
    ApplicationTechnology.ELECTRON: AdapterType.ELECTRON_PLAYWRIGHT,
    ApplicationTechnology.CITRIX: AdapterType.SIKULI_IMAGE,
    ApplicationTechnology.RDP: AdapterType.SIKULI_IMAGE,
    ApplicationTechnology.PACKAGED: AdapterType.FLAUI,
    ApplicationTechnology.UNKNOWN: AdapterType.FLAUI,
}


def _build_rules() -> list[ClassifierRule]:
    """
    Return the full ordered list of classifier rules.
    Rules for the same technology are additive — each match raises confidence.
    """
    return [
        # ----------------------------------------------------------------
        # WPF
        # ----------------------------------------------------------------
        ClassifierRule(
            technology=ApplicationTechnology.WPF,
            name="wpf_modules",
            weight=0.5,
            probe=lambda s: s.has_module(
                "presentationcore.dll",
                "presentationframework.dll",
            ),
            description="PresentationCore / PresentationFramework DLLs loaded",
        ),
        ClassifierRule(
            technology=ApplicationTechnology.WPF,
            name="wpf_window_class",
            weight=0.4,
            probe=lambda s: s.has_window_class_prefix("HwndWrapper"),
            description="Top-level window class starts with 'HwndWrapper' (WPF default)",
        ),
        ClassifierRule(
            technology=ApplicationTechnology.WPF,
            name="wpf_dotnet",
            weight=0.1,
            probe=lambda s: s.is_dotnet,
            description=".NET assembly (supporting evidence for WPF)",
        ),

        # ----------------------------------------------------------------
        # WinForms
        # ----------------------------------------------------------------
        ClassifierRule(
            technology=ApplicationTechnology.WINFORMS,
            name="winforms_modules",
            weight=0.5,
            probe=lambda s: s.has_module("system.windows.forms.dll"),
            description="System.Windows.Forms DLL loaded",
        ),
        ClassifierRule(
            technology=ApplicationTechnology.WINFORMS,
            name="winforms_window_class",
            weight=0.4,
            probe=lambda s: s.has_window_class_prefix(
                "WindowsForms10.",
                "WindowsForms",
            ),
            description="Top-level window class starts with 'WindowsForms10.' (WinForms default)",
        ),
        ClassifierRule(
            technology=ApplicationTechnology.WINFORMS,
            name="winforms_dotnet",
            weight=0.1,
            probe=lambda s: s.is_dotnet,
            description=".NET assembly (supporting evidence for WinForms)",
        ),

        # ----------------------------------------------------------------
        # WinUI 3
        # ----------------------------------------------------------------
        ClassifierRule(
            technology=ApplicationTechnology.WINUI3,
            name="winui3_modules",
            weight=0.6,
            probe=lambda s: s.has_module("microsoft.ui.xaml.dll"),
            description="Microsoft.UI.Xaml DLL loaded",
        ),
        ClassifierRule(
            technology=ApplicationTechnology.WINUI3,
            name="winui3_window_class",
            weight=0.4,
            probe=lambda s: s.has_window_class_containing("Microsoft.UI.Xaml"),
            description="Window class contains 'Microsoft.UI.Xaml'",
        ),

        # ----------------------------------------------------------------
        # MAUI
        # ----------------------------------------------------------------
        ClassifierRule(
            technology=ApplicationTechnology.MAUI,
            name="maui_modules",
            weight=0.7,
            probe=lambda s: s.has_module(
                "microsoft.maui.dll",
                "microsoft.maui.controls.dll",
            ),
            description="Microsoft.Maui DLL loaded",
        ),
        ClassifierRule(
            technology=ApplicationTechnology.MAUI,
            name="maui_window_class",
            weight=0.3,
            probe=lambda s: s.has_window_class_containing("MAUI"),
            description="Window class contains 'MAUI'",
        ),

        # ----------------------------------------------------------------
        # Electron
        # ----------------------------------------------------------------
        ClassifierRule(
            technology=ApplicationTechnology.ELECTRON,
            name="electron_modules",
            weight=0.4,
            probe=lambda s: s.has_module("node.dll", "libnode.dll"),
            description="Node.js DLL loaded (Electron runtime)",
        ),
        ClassifierRule(
            technology=ApplicationTechnology.ELECTRON,
            name="electron_window_class",
            weight=0.4,
            probe=lambda s: s.has_window_class_containing("Chrome_WidgetWin"),
            description="Window class is Chrome_WidgetWin_* (Chromium/Electron)",
        ),
        ClassifierRule(
            technology=ApplicationTechnology.ELECTRON,
            name="electron_exe_name",
            weight=0.2,
            probe=lambda s: s.exe_matches("electron.exe", "*electron*.exe"),
            description="Executable name matches Electron pattern",
        ),

        # ----------------------------------------------------------------
        # Java Swing / AWT
        # ----------------------------------------------------------------
        ClassifierRule(
            technology=ApplicationTechnology.JAVA_SWING,
            name="java_swing_modules",
            weight=0.5,
            probe=lambda s: s.has_module("jvm.dll", "awt.dll"),
            description="JVM + AWT DLLs loaded",
        ),
        ClassifierRule(
            technology=ApplicationTechnology.JAVA_SWING,
            name="java_swing_window_class",
            weight=0.4,
            probe=lambda s: s.has_window_class_containing("SunAwtFrame", "SunAwtDialog"),
            description="Window class is SunAwtFrame / SunAwtDialog (Swing default)",
        ),
        ClassifierRule(
            technology=ApplicationTechnology.JAVA_SWING,
            name="java_exe",
            weight=0.1,
            probe=lambda s: s.exe_matches("java.exe", "javaw.exe", "java"),
            description="Executable is java.exe / javaw.exe",
        ),

        # ----------------------------------------------------------------
        # Qt
        # ----------------------------------------------------------------
        ClassifierRule(
            technology=ApplicationTechnology.QT,
            name="qt_modules_qt5",
            weight=0.5,
            probe=lambda s: s.has_module("qt5core.dll", "qt5widgets.dll"),
            description="Qt5 DLLs loaded",
        ),
        ClassifierRule(
            technology=ApplicationTechnology.QT,
            name="qt_modules_qt6",
            weight=0.5,
            probe=lambda s: s.has_module("qt6core.dll", "qt6widgets.dll"),
            description="Qt6 DLLs loaded",
        ),
        ClassifierRule(
            technology=ApplicationTechnology.QT,
            name="qt_window_class",
            weight=0.4,
            probe=lambda s: s.has_window_class_containing("Qt5", "Qt6QWindow"),
            description="Window class contains Qt5 / Qt6QWindow",
        ),

        # ----------------------------------------------------------------
        # Citrix / RDP (image-based)
        # ----------------------------------------------------------------
        ClassifierRule(
            technology=ApplicationTechnology.CITRIX,
            name="citrix_exe",
            weight=0.7,
            probe=lambda s: s.exe_matches(
                "wfica32.exe", "selfservice.exe", "receiver.exe",
                "storebrowse.exe", "concentr.exe",
            ),
            description="Citrix Workspace / Receiver executable",
        ),
        ClassifierRule(
            technology=ApplicationTechnology.CITRIX,
            name="citrix_modules",
            weight=0.3,
            probe=lambda s: s.has_module("ctxmui.dll", "nrica.dll"),
            description="Citrix DLLs loaded",
        ),
        ClassifierRule(
            technology=ApplicationTechnology.RDP,
            name="rdp_exe",
            weight=0.9,
            probe=lambda s: s.exe_matches("mstsc.exe"),
            description="Microsoft Remote Desktop executable",
        ),

        # ----------------------------------------------------------------
        # Windows Packaged (MSIX / Store)
        # ----------------------------------------------------------------
        ClassifierRule(
            technology=ApplicationTechnology.PACKAGED,
            name="packaged_modules",
            weight=0.7,
            probe=lambda s: s.has_module(
                "windowsappruntime.main.dll",
                "microsoft.windowsappruntime.dll",
            ),
            description="Windows App Runtime DLLs loaded",
        ),

        # ----------------------------------------------------------------
        # Win32 (fallback — no positive signals for managed / JVM runtimes)
        # ----------------------------------------------------------------
        ClassifierRule(
            technology=ApplicationTechnology.WIN32,
            name="win32_no_dotnet_no_java",
            weight=0.4,
            probe=lambda s: (
                not s.is_dotnet
                and not s.has_module("jvm.dll")
                and not s.has_module("node.dll", "libnode.dll")
                and not s.has_module("qt5core.dll", "qt6core.dll")
            ),
            description="No managed / JVM / Qt / Electron runtime signals",
        ),
        ClassifierRule(
            technology=ApplicationTechnology.WIN32,
            name="win32_kernel_only",
            weight=0.3,
            probe=lambda s: s.has_module("kernel32.dll", "user32.dll"),
            description="Only native Win32 DLLs in module list",
        ),
    ]


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


class TechnologyClassifier:
    """
    Runs all registered rules against a ``ProcessSignals`` snapshot and
    returns a ranked ``DetectionResult``.
    """

    def __init__(self) -> None:
        self._rules: list[ClassifierRule] = _build_rules()

    def classify(self, signals: ProcessSignals) -> DetectionResult:
        """
        Score all technologies and return the highest-confidence result.

        Confidence is capped at 1.0 per technology (additive rule weights
        for the same technology may exceed 1.0 before capping).
        """
        scores: dict[ApplicationTechnology, float] = {}
        evidence: dict[ApplicationTechnology, list[str]] = {}

        for rule in self._rules:
            try:
                if rule.probe(signals):
                    scores[rule.technology] = min(
                        1.0,
                        scores.get(rule.technology, 0.0) + rule.weight,
                    )
                    evidence.setdefault(rule.technology, []).append(rule.description)
            except Exception:
                pass  # individual rule failures must not crash detection

        if not scores:
            return DetectionResult(
                technology=ApplicationTechnology.UNKNOWN,
                confidence=0.0,
                recommended_adapter=AdapterType.FLAUI,
                evidence=["No classification signals matched"],
            )

        best_tech = max(scores, key=lambda t: scores[t])
        best_score = scores[best_tech]

        return DetectionResult(
            technology=best_tech,
            confidence=round(best_score, 3),
            recommended_adapter=_TECHNOLOGY_ADAPTER_MAP.get(best_tech, AdapterType.FLAUI),
            evidence=evidence.get(best_tech, []),
            metadata={
                "all_scores": {t.value: round(s, 3) for t, s in scores.items()},
            },
        )
