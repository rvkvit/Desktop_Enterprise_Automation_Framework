#!/usr/bin/env python3
"""
Desktop Automation Platform — Project Scaffolding Tool

Generates a fully-structured, style-guide-compliant test project in one command.

Usage
-----
    python scripts/new_project.py \\
        --name "Claims Desktop" \\
        --executable "C:\\Apps\\Claims\\ClaimsDesktop.exe" \\
        --screens login claims_entry dashboard \\
        --output C:\\Projects\\claims-automation

    python scripts/new_project.py --help

What gets created
-----------------
    <output>/
    ├── config.yaml
    ├── .gitignore
    ├── screens/
    │   └── <screen>/
    │       ├── locators.yaml
    │       └── keywords.resource
    ├── resources/
    │   ├── platform_settings.resource
    │   └── business_keywords.resource
    └── tests/
        └── test_<screen>.robot       (one per screen)
"""

from __future__ import annotations

import argparse
import re
import sys
import textwrap
from pathlib import Path


# ---------------------------------------------------------------------------
# Name helpers
# ---------------------------------------------------------------------------

def slugify(name: str) -> str:
    """'Claims Desktop' → 'claims_desktop'"""
    return re.sub(r"[^\w]+", "_", name.strip().lower()).strip("_")


def title_case(slug: str) -> str:
    """'claims_entry' → 'Claims Entry'"""
    return slug.replace("_", " ").title()


def namespace(slug: str) -> str:
    """'claims_entry' → 'CLAIMS_ENTRY'"""
    return slug.upper()


# ---------------------------------------------------------------------------
# File templates
# ---------------------------------------------------------------------------

def _config_yaml(app_name: str, executable: str) -> str:
    return textwrap.dedent(f"""\
        framework:
          adapter_mode: flaui          # flaui | winappdriver | pywinauto | playwright
          retry_count: 2
          screenshot_on_failure: true
          logging_level: INFO

        application:
          name: {app_name}
          executable: {executable}
          launch_timeout_seconds: 15
          # window_title: "Optional — title of the main window"
          # working_directory: "Optional"
          # launch_arguments:
          #   - "--env=UAT"
          # environment:
          #   MY_ENV_VAR: "${{MY_ENV_VAR}}"
    """)


def _gitignore() -> str:
    return textwrap.dedent("""\
        # Robot Framework output — generated at runtime, never commit
        reports/
        output.xml
        log.html
        report.html

        # Python
        *.pyc
        __pycache__/
        .env
    """)


def _screen_locators_yaml(screen_slug: str) -> str:
    ns = namespace(screen_slug)
    title = title_case(screen_slug)
    return textwrap.dedent(f"""\
        # {title} screen — element locators
        #
        # Keys here are automatically namespaced as {ns}.<KEY> when loaded by the platform.
        # Strategy priority: automation_id > name > control_type > class_name > xpath > image
        # Always provide at least one fallback strategy.
        #
        # Replace the examples below with real element identifiers for your application.
        # Run 'Scan Application Screen' from a Robot test to auto-discover elements.

        EXAMPLE_BUTTON:
          primary:
            strategy: automation_id
            value: "btnExample"
          fallback:
            - strategy: name
              value: "Example"
          metadata:
            description: Replace — example button on the {title} screen

        EXAMPLE_FIELD:
          primary:
            strategy: automation_id
            value: "txtExample"
          fallback:
            - strategy: name
              value: "Example Field"
          metadata:
            description: Replace — example text input on the {title} screen

        EXAMPLE_LABEL:
          primary:
            strategy: automation_id
            value: "lblExample"
          fallback:
            - strategy: name
              value: "Example Label"
            - strategy: control_type
              value: "Text"
          metadata:
            description: Replace — example status/read-only label on the {title} screen
    """)


def _screen_keywords_resource(screen_slug: str) -> str:
    ns = namespace(screen_slug)
    title = title_case(screen_slug)
    return textwrap.dedent(f"""\
        *** Settings ***
        Resource    ../../resources/platform_settings.resource

        *** Keywords ***
        Click Example Button
            [Documentation]    Clicks the example button on the {title} screen.
            Click    {ns}.EXAMPLE_BUTTON

        Enter Example Text
            [Documentation]    Types text into the example field on the {title} screen.
            [Arguments]    ${{text}}
            Input Text    {ns}.EXAMPLE_FIELD    ${{text}}

        Read Example Label
            [Documentation]    Returns the current text of the example label.
            ${{value}}=    Get Text    {ns}.EXAMPLE_LABEL
            RETURN    ${{value}}
    """)


def _platform_settings_resource() -> str:
    return textwrap.dedent("""\
        *** Settings ***
        Library    DesktopAutomationLibrary    config_path=${CURDIR}/../config.yaml
        ...                                   locator_path=${CURDIR}/../screens
    """)


def _business_keywords_resource(screen_slugs: list[str]) -> str:
    screen_imports = "\n".join(
        f"Resource    ../screens/{s}/keywords.resource"
        for s in screen_slugs
    )
    first_title = title_case(screen_slugs[0]) if screen_slugs else "Main"

    return textwrap.dedent(f"""\
        *** Settings ***
        Resource    platform_settings.resource
        {screen_imports}

        *** Keywords ***
        # ---------------------------------------------------------------------------
        # Add business-level keywords here.
        # Business keywords compose screen keywords into workflows.
        # They must NOT call platform keywords (Input Text, Click, etc.) directly.
        # ---------------------------------------------------------------------------

        # Example — replace with real workflows:
        #
        # Complete {first_title} Workflow
        #     [Documentation]    Example business workflow — replace with real steps.
        #     [Arguments]    ${{example_value}}
        #     Launch Application
        #     Enter Example Text    ${{example_value}}
        #     Click Example Button
        #
        # Verify Result Is Shown
        #     [Documentation]    Asserts the result label contains the expected value.
        #     [Arguments]    ${{expected}}
        #     ${{actual}}=    Read Example Label
        #     Should Contain    ${{actual}}    ${{expected}}
    """)


def _test_robot(screen_slug: str) -> str:
    title = title_case(screen_slug)
    return textwrap.dedent(f"""\
        *** Settings ***
        Resource         ../resources/business_keywords.resource
        Suite Teardown   Close Application

        *** Test Cases ***
        {title} Smoke Test
            [Documentation]    Replace with a real test scenario for the {title} screen.
            ...                Test files must contain ONLY business keyword calls.
            [Tags]    smoke    {screen_slug}
            Launch Application
            # Add your business keyword calls below — no platform keywords, no locator names:
            # Complete {title} Workflow    example_value
            # Verify Result Is Shown       expected_result

        {title} Regression Test
            [Documentation]    Replace with a regression scenario.
            [Tags]    regression    {screen_slug}
            Launch Application
            # Add regression keyword calls here
    """)


# ---------------------------------------------------------------------------
# Project generator
# ---------------------------------------------------------------------------

class ProjectScaffolder:

    def __init__(
        self,
        output_dir: Path,
        app_name: str,
        executable: str,
        screen_slugs: list[str],
        force: bool = False,
    ) -> None:
        self.root = output_dir
        self.app_name = app_name
        self.executable = executable
        self.screens = screen_slugs
        self.force = force
        self._created: list[Path] = []

    def run(self) -> None:
        self._check_output_dir()
        self._write_root_files()
        self._write_screens()
        self._write_resources()
        self._write_tests()
        self._print_summary()

    # ------------------------------------------------------------------

    def _check_output_dir(self) -> None:
        if self.root.exists() and any(self.root.iterdir()):
            if not self.force:
                print(
                    f"\n[!!] Output directory already exists and is not empty: {self.root}\n"
                    f"     Use --force to overwrite.\n"
                )
                sys.exit(1)
            print(f"[!!] Overwriting existing directory: {self.root}")
        self.root.mkdir(parents=True, exist_ok=True)

    def _write(self, rel_path: str, content: str) -> None:
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        self._created.append(path)

    def _write_root_files(self) -> None:
        self._write("config.yaml", _config_yaml(self.app_name, self.executable))
        self._write(".gitignore", _gitignore())
        (self.root / "reports" / "screenshots" / "failures").mkdir(parents=True, exist_ok=True)

    def _write_screens(self) -> None:
        for slug in self.screens:
            self._write(f"screens/{slug}/locators.yaml", _screen_locators_yaml(slug))
            self._write(f"screens/{slug}/keywords.resource", _screen_keywords_resource(slug))

    def _write_resources(self) -> None:
        self._write("resources/platform_settings.resource", _platform_settings_resource())
        self._write("resources/business_keywords.resource", _business_keywords_resource(self.screens))

    def _write_tests(self) -> None:
        for slug in self.screens:
            self._write(f"tests/test_{slug}.robot", _test_robot(slug))

    def _print_summary(self) -> None:
        print(f"\n  Project scaffolded successfully!")
        print(f"  Location : {self.root}")
        print(f"  App      : {self.app_name}")
        print(f"  Screens  : {', '.join(title_case(s) for s in self.screens)}")
        print(f"\n  Files created ({len(self._created)}):")
        for f in self._created:
            print(f"    {f.relative_to(self.root)}")
        print()
        print("  Next steps:")
        print("  1. Update config.yaml with your application details")
        print("  2. Replace locators in each screens/<name>/locators.yaml")
        print("     (launch the app and run 'Scan Application Screen' to auto-discover)")
        print("  3. Replace example screen keywords with real ones")
        print("  4. Write business keywords in resources/business_keywords.resource")
        print("  5. Write test cases in tests/ — business keywords only")
        print(f"  6. Run: robot {self.root / 'tests'}")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="new_project.py",
        description=(
            "Desktop Automation Platform — project scaffolding tool.\n"
            "Generates a style-guide-compliant project structure in one command."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python scripts/new_project.py \\
                  --name "Claims Desktop" \\
                  --executable "C:\\\\Apps\\\\Claims\\\\ClaimsDesktop.exe" \\
                  --screens login claims_entry dashboard \\
                  --output C:\\\\Projects\\\\claims-automation

              python scripts/new_project.py \\
                  --name "HR Portal" \\
                  --executable "C:\\\\Apps\\\\HR\\\\HRPortal.exe" \\
                  --screens login employee_search leave_request \\
                  --output .\\\\hr_automation
        """),
    )
    parser.add_argument(
        "--name", "-n",
        required=True,
        metavar="APP_NAME",
        help='Human-readable application name (e.g. "Claims Desktop")',
    )
    parser.add_argument(
        "--executable", "-e",
        required=True,
        metavar="PATH",
        help=r'Full path to the application executable (e.g. "C:\Apps\Claims\ClaimsDesktop.exe")',
    )
    parser.add_argument(
        "--screens", "-s",
        nargs="+",
        required=True,
        metavar="SCREEN",
        help=(
            "One or more screen names in snake_case "
            "(e.g. login claims_entry dashboard). "
            "Each generates a screens/<name>/ folder."
        ),
    )
    parser.add_argument(
        "--output", "-o",
        default=".",
        metavar="DIR",
        help="Directory to create the project in (default: current directory)",
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite output directory if it already exists",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # Normalise screen names to snake_case
    screen_slugs = [slugify(s) for s in args.screens]
    invalid = [s for s in screen_slugs if not s]
    if invalid:
        print(f"[XX] Could not normalise screen names: {args.screens}")
        sys.exit(1)

    output_dir = Path(args.output).resolve()

    print(f"\n  Desktop Automation Platform — Project Scaffolding")
    print(f"  =================================================")
    print(f"  App name   : {args.name}")
    print(f"  Executable : {args.executable}")
    print(f"  Screens    : {', '.join(title_case(s) for s in screen_slugs)}")
    print(f"  Output     : {output_dir}\n")

    scaffolder = ProjectScaffolder(
        output_dir=output_dir,
        app_name=args.name,
        executable=args.executable,
        screen_slugs=screen_slugs,
        force=args.force,
    )
    scaffolder.run()


if __name__ == "__main__":
    main()
