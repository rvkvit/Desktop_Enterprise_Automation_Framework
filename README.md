# Desktop Automation Platform

**Automate any Windows desktop application — without knowing which technology it was built with.**

This platform lets QA teams write one set of tests that work across WPF, WinForms, WinUI 3, MAUI, Java Swing, Electron, Citrix, legacy Win32, and more. You do not need to know what technology your application uses — the platform detects it automatically.

---

## Table of Contents

1. [Do I need to do the entire setup?](#1-do-i-need-to-do-the-entire-setup)
2. [What you need before starting](#2-what-you-need-before-starting-prerequisites)
3. [Step-by-step installation](#3-step-by-step-installation)
4. [Your first test in 10 minutes](#4-your-first-test-in-10-minutes)
5. [How the framework is organised](#5-how-the-framework-is-organised)
6. [Which adapter should I use?](#6-which-adapter-should-i-use)
7. [Configure the framework](#7-configure-the-framework-configyaml)
8. [Define your UI elements (locators)](#8-define-your-ui-elements-locators)
9. [Write Robot Framework tests](#9-write-robot-framework-tests)
10. [Run your tests](#10-run-your-tests)
11. [Understanding the reports](#11-understanding-the-reports)
12. [Troubleshooting](#12-troubleshooting)
13. [FAQ](#13-faq)

---

## 1. Do I need to do the entire setup?

**Yes, but it is a one-time activity and takes about 20–30 minutes.**

After setup, using the framework is as simple as:
1. Writing a small YAML config file (5 lines)
2. Writing a small YAML file listing your app's buttons and fields
3. Writing test steps in plain English using Robot Framework

The setup installs Python, a few libraries, and the FlaUI automation engine. You run a single script and it does everything automatically.

> **If you are on a managed corporate machine** and cannot install software yourself, ask your IT team to follow the [Corporate IT Setup](#corporate-it-setup) section at the bottom of this page.

---

## 2. What you need before starting (Prerequisites)

| What | Why | How to check |
|------|-----|--------------|
| **Windows 10 or 11** (64-bit) | The framework automates Windows desktop apps | Right-click Start → System |
| **Python 3.10 or newer** | The framework is written in Python | Open a terminal: `python --version` |
| **.NET 6 Runtime or newer** | Required for the FlaUI adapter (WPF/WinForms/Win32) | `dotnet --version` |
| **Git** (optional but recommended) | To clone this repository | `git --version` |
| **Robot Framework** | The test writing language | Installed automatically |
| **Administrator access** | Needed to automate some desktop apps | Talk to IT if you don't have it |

### Quick check — run this in a terminal:

```powershell
python --version        # Must say 3.10 or higher
dotnet --version        # Must say 6.0 or higher
```

If Python is missing, download it from **python.org** → choose "Windows installer (64-bit)" → tick "Add Python to PATH" during install.

If .NET is missing, download the **.NET 6 Runtime** from **dotnet.microsoft.com/download**.

---

## 3. Step-by-step installation

### Option A — Automatic (recommended)

Open PowerShell **as Administrator** and run:

```powershell
# 1. Go to the framework folder
cd "C:\Path\To\Desktop-Claude-Enterprise-Autoamtion-Framework"

# 2. Run the one-click installer
.\scripts\install.ps1
```

The script will:
- Create a Python virtual environment
- Install all Python dependencies
- Download FlaUI automation assemblies via NuGet
- Verify the installation

That's it. Skip to [Section 4](#4-your-first-test-in-10-minutes).

---

### Option B — Manual (if the script doesn't work)

**Step 1 — Open a terminal in the framework folder**

```powershell
cd "C:\Path\To\Desktop-Claude-Enterprise-Autoamtion-Framework"
```

**Step 2 — Create a virtual environment (keeps everything isolated)**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

You will see `(.venv)` appear at the start of your prompt. This means the virtual environment is active.

> **Why a virtual environment?** It keeps this framework's libraries separate from anything else on your machine. Think of it as a clean room.

**Step 3 — Install Python dependencies**

```powershell
pip install -r requirements.txt
```

This installs Robot Framework, Pydantic, structlog, and all other libraries. It may take 2–5 minutes.

**Step 4 — Download FlaUI assemblies**

```powershell
.\scripts\setup_flaui.ps1
```

This downloads the FlaUI .NET automation library into `lib\flaui\`.

**Step 5 — Verify the installation**

```powershell
python -c "import robot; print('Robot Framework OK')"
python -c "import pydantic; print('Pydantic OK')"
python -c "import clr; print('pythonnet OK')"
```

All three lines should print `OK`. If `pythonnet` fails, run:
```powershell
pip install pythonnet
```
Then retry. If any other check fails, see [Troubleshooting](#12-troubleshooting).

---

## 4. Your first test in 10 minutes

The repository already contains a complete, ready-to-run example project at `my_first_test\`. You do not need to create any files — just activate the virtual environment and run.

### Step 1 — Activate the virtual environment

```powershell
cd "C:\Path\To\Desktop-Claude-Enterprise-Autoamtion-Framework"
.venv\Scripts\Activate.ps1
```

You will see `(.venv)` at the start of your prompt. Every time you open a new terminal you must do this before running tests.

### Step 2 — Run the example test

```powershell
cd my_first_test
robot test_notepad.robot
```

Notepad will open, the framework will type text into it, verify the text appeared, and close Notepad. The terminal will show:

```
Test Notepad
Type Text Into Notepad And Verify                                     | PASS |
Test Notepad                                                  1 passed, 0 failed
```

### Step 3 — See the results

Open `my_first_test\reports\report.html` in any browser.

> **If you see `AdapterInitializationException: clr is not installed`** — pythonnet is missing.
> Run this once and retry:
> ```powershell
> pip install pythonnet
> ```

> **If you see `Resource file '...' does not exist`** — you are running the test from the wrong
> folder. Always `cd my_first_test` first, then run `robot test_notepad.robot`.

### What the example project looks like

```
my_first_test\
├── config.yaml                        ← tells the framework about Notepad
├── screens\
│   └── notepad\
│       ├── locators.yaml              ← where the text area and title bar are
│       └── keywords.resource          ← screen-level actions (Enter Text In Editor, etc.)
├── resources\
│   ├── platform_settings.resource     ← imports DesktopAutomationLibrary (one place only)
│   └── business_keywords.resource     ← business-level keywords (Open Notepad And Type, etc.)
└── test_notepad.robot                 ← the test — only calls business keywords
```

This three-tier structure is what every project built on this framework follows. The [Style Guide](docs/STYLE_GUIDE.md) explains each tier in detail.

### Ready to automate your own application?

Use the scaffolding tool — it creates the correct folder structure in seconds:

```powershell
python scripts\new_project.py `
    --name "My Application" `
    --executable "C:\Apps\MyApp.exe" `
    --screens login main_screen `
    --output C:\Projects\my-app-tests
```

Then see [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) for the full step-by-step guide.

---

## 5. How the framework is organised

```
Desktop-Claude-Enterprise-Autoamtion-Framework\
│
├── requirements.txt            ← List of Python libraries (do not edit)
├── scripts\
│   ├── install.ps1             ← One-click installer
│   ├── setup_flaui.ps1         ← Downloads FlaUI assemblies
│   └── new_project.py          ← Scaffolding tool — generates a new project skeleton
│
├── examples\
│   ├── notepad_reference\      ← Complete single-screen reference project (study this first)
│   └── claims_reference\       ← Multi-screen reference project (3 screens, generated by scaffolder)
│
└── desktop_automation_platform\   ← The framework itself (do not edit)
    ├── core\                   ← Core building blocks (models, interfaces, exceptions)
    ├── adapters\               ← One adapter per application technology
    │   ├── flaui\              ← WPF, WinForms, WinUI3, MAUI, Win32 (UIA-based)
    │   ├── pywinauto\          ← Win32, Qt, MFC, legacy VB6/Delphi apps
    │   ├── winappdriver\       ← WPF, WinForms, WinUI3, UWP via Appium/WebDriver
    │   ├── electron_playwright\← Electron apps (VS Code, Teams, Slack, etc.)
    │   ├── java_access_bridge\ ← Java Swing / AWT apps
    │   └── sikuli_image\       ← Citrix / RDP (image-based, no accessibility tree)
    ├── scanner\                ← Automatic locator discovery engine
    ├── recovery\               ← Self-healing locator strategies and reporting
    ├── config\                 ← Config loading and validation
    ├── locator_engine\         ← Reads and namespaces your locators.yaml files
    └── robot_keywords\         ← The keywords you use in .robot files
```

**The three files you create for every project:**

| File | What it does | How often |
|------|-------------|-----------|
| `config.yaml` | Tells the framework about your app and how to behave | Once per app |
| `locators.yaml` | Lists every button/field/menu you want to interact with | Updated as app changes |
| `tests\*.robot` | Contains your test cases in plain English | Written by QA |

---

## 6. Which adapter should I use?

**In most cases: set `adapter_mode: auto` and the platform detects it automatically.**

If auto-detection doesn't work (or you want to be explicit), use this table:

| Your application | Set `type:` to | Adapter used automatically | Notes |
|-----------------|---------------|---------------------------|-------|
| WPF app (.NET) | `wpf` | FlaUI | Best choice for .NET apps |
| WinForms app (.NET) | `winforms` | FlaUI | Best choice for .NET apps |
| WinUI 3 app | `winui3` | FlaUI or WinAppDriver | FlaUI recommended |
| .NET MAUI desktop | `maui` | FlaUI | |
| UWP app (Windows Store) | `uwp` | WinAppDriver | Requires WinAppDriver.exe running |
| Old Windows app (Win32) | `win32` | pywinauto | Win32 or FlaUI, auto-selected |
| Legacy MFC / VB6 / Delphi | `mfc` | pywinauto (win32 backend) | |
| Qt desktop app | `qt` | pywinauto | |
| Java Swing / AWT | `java_swing` | Java Access Bridge | |
| Electron (VS Code, Slack, etc.) | `electron` | Playwright | |
| Citrix virtual desktop | `citrix` | Sikuli (image-based) | |
| RDP remote desktop | `rdp` | Sikuli (image-based) | |
| Not sure | `auto` | Auto-detected | Platform inspects the process |

### How to check what technology your app uses

1. Open **Task Manager** (Ctrl+Shift+Esc)
2. Find your app in the list
3. Right-click → "Open file location"
4. If the folder contains `.dll` files starting with `Presentation` → it's **WPF**
5. If it contains `System.Windows.Forms.dll` → it's **WinForms**
6. If it runs inside a browser-like window → it's probably **Electron**

Or just leave it as `auto` — the platform will figure it out.

---

## 7. Configure the framework (`config.yaml`)

The config file controls how the framework behaves. Here is every option explained in plain English:

```yaml
# ─────────────────────────────────────────────────────────
# FRAMEWORK SECTION — how the platform behaves overall
# ─────────────────────────────────────────────────────────
framework:
  adapter_mode: auto    # auto = detect automatically (recommended)
                        # Other options: flaui, pywinauto, electron_playwright,
                        #                java_access_bridge, sikuli_image

  retry_count: 3        # If a step fails, how many times to retry?
                        # 0 = no retries, 3 = retry 3 more times (4 total)

  screenshot_on_failure: true    # Take a screenshot when a step fails?
                                 # Screenshots go to reporting.screenshots_directory

  logging_level: INFO   # How much detail in the log?
                        # DEBUG = maximum detail (slow, use when debugging)
                        # INFO  = normal (recommended)
                        # ERROR = only errors

  detection_confidence_threshold: 0.6   # How confident the auto-detector must be
                                        # before trusting its result (0.0 to 1.0)
                                        # Leave at 0.6 unless you have problems

# ─────────────────────────────────────────────────────────
# APPLICATION SECTION — about your app
# ─────────────────────────────────────────────────────────
application:
  name: Claims Desktop      # Any name you choose — appears in reports

  executable: C:\Apps\claims.exe    # Full path to your .exe file
                                    # Use ${MY_EXE} to read from environment variable

  type: auto                # See table in Section 6

  window_title: Claims Processing   # Part of the window title (optional)
                                    # Used when attaching to a running app

  launch_timeout_seconds: 30   # How many seconds to wait for the app to open?

# ─────────────────────────────────────────────────────────
# EXECUTION SECTION — timing and waiting
# ─────────────────────────────────────────────────────────
execution:
  timeout: 30          # Wait up to 30 seconds for any element to appear
  poll_interval: 0.5   # Check every half second while waiting

# ─────────────────────────────────────────────────────────
# REPORTING SECTION — where to save output
# ─────────────────────────────────────────────────────────
reporting:
  output_directory: reports                      # Where to save test reports
  screenshots_directory: reports\screenshots     # Where to save screenshots
```

### Using environment variables in config

Instead of hardcoding paths, use `${VARIABLE_NAME}`:

```yaml
application:
  executable: ${CLAIMS_APP_EXE}    # Read from environment variable
```

Then set the variable before running tests:

```powershell
$env:CLAIMS_APP_EXE = "C:\Apps\claims.exe"
robot tests\
```

This is useful in CI/CD pipelines where the path changes per environment.

---

## 8. Define your UI elements (locators)

The `locators.yaml` file is a dictionary of every button, field, and menu in your app. Each entry has a **name** you choose and a **strategy** for finding it.

### Understanding strategies

| Strategy | What it finds by | Best for |
|----------|-----------------|----------|
| `automation_id` | The element's internal ID (most reliable) | WPF, WinForms, WinUI3 |
| `name` | The text visible on the element | Buttons with labels |
| `class_name` | The technical class name of the control | Win32, WinForms |
| `control_type` | The type of control (Button, TextBox, etc.) | When combined with other strategies |
| `text` | Exact visible text | Labels, static text |
| `partial_text` | Any element containing this text | When exact text varies |
| `image` | A screenshot of what it looks like | Citrix / RDP only |

### How to find the automation_id of an element

**Method 1 — Use the built-in scanner** (recommended):

Add a temporary test (e.g. `tests\scan_screens.robot`) and run it once:

```robotframework
*** Settings ***
Library    DesktopAutomationLibrary
...        config_path=${CURDIR}/../config.yaml
...        locator_path=${CURDIR}/../screens

*** Test Cases ***
Scan My Screen
    Launch Application
    Scan Application Screen    output_path=${CURDIR}/../screens/my_screen/locators.yaml
    Close Application
```

Use `${CURDIR}` for all paths — it resolves to the folder containing the `.robot` file, so the paths work regardless of where `robot` is run from.

The platform will walk every element visible on screen and write a ready-to-use `locators.yaml` with suggested names, strategies, and scores. Review the generated file, rename keys to match your naming convention, delete anything you will not use, and delete the temporary test.

**Method 2 — Use FlaUI Inspect** (free tool):
1. Download **FlaUI Inspect** from GitHub: `github.com/FlaUI/FlaUI`
2. Run `FlaUiInspect.exe`
3. Hover over any element in your app
4. The right panel shows `AutomationId`, `Name`, `ClassName`
5. Copy those values into your `locators.yaml`

**Method 3 — Use Microsoft Accessibility Insights**:
1. Download from `accessibilityinsights.io`
2. Click the element in your app
3. Note the `AutomationId` value

### Writing locators

```yaml
# Simple locator — finds by automation ID
LOGIN_BUTTON:
  primary:
    strategy: automation_id
    value: btnLogin          # The AutomationId from the inspection tool

# Locator with fallbacks — tries automation_id first, then name, then image
SAVE_BUTTON:
  primary:
    strategy: automation_id
    value: btnSave
  fallbacks:
    - strategy: name
      value: Save
    - strategy: name
      value: Save Changes
    - strategy: image
      value: images\save_button.png    # Only used for Citrix/RDP

# Locator with custom timeout (this element takes 15 seconds to load)
REPORT_GRID:
  primary:
    strategy: automation_id
    value: dgReports
    timeout: 15               # Wait up to 15 seconds for this one element

# Locator inside a panel (scope limits the search area)
SEARCH_BUTTON:
  primary:
    strategy: automation_id
    value: btnSearch
  scope: SEARCH_PANEL         # Only look inside the element named SEARCH_PANEL

SEARCH_PANEL:
  primary:
    strategy: automation_id
    value: pnlSearch
```

### Naming conventions

Use `UPPER_SNAKE_CASE` and group by screen:

```yaml
# ── Login Screen ─────────────────────────────────────────
LOGIN_USERNAME:
  primary:
    strategy: automation_id
    value: txtUsername

LOGIN_PASSWORD:
  primary:
    strategy: automation_id
    value: txtPassword

LOGIN_BUTTON:
  primary:
    strategy: automation_id
    value: btnLogin

# ── Dashboard Screen ─────────────────────────────────────
DASHBOARD_WELCOME_TEXT:
  primary:
    strategy: name
    value: Welcome

DASHBOARD_NEW_CLAIM_BUTTON:
  primary:
    strategy: automation_id
    value: btnNewClaim
```

---

## 9. Write Robot Framework tests

Robot Framework uses a simple table format. You write test steps in plain English.

### Basic structure

```robotframework
*** Settings ***
Library    desktop_automation_platform.robot_keywords.DesktopKeywords

*** Variables ***
${CONFIG}      config.yaml
${LOCATORS}    locators.yaml

*** Test Cases ***
User Can Log In Successfully
    [Documentation]    Verifies that a valid user can log into the application
    Launch Application    ${CONFIG}    ${LOCATORS}
    Wait For Element      LOGIN_USERNAME
    Input Text            LOGIN_USERNAME    john.doe@company.com
    Input Text            LOGIN_PASSWORD    Password123!
    Click Element         LOGIN_BUTTON
    Wait For Element      DASHBOARD_WELCOME_TEXT
    ${text}=    Get Text  DASHBOARD_WELCOME_TEXT
    Should Contain        ${text}    Welcome
    [Teardown]    Close Application
```

### All available keywords

| Keyword | What it does | Example |
|---------|-------------|---------|
| `Launch Application` | Opens the app | `Launch Application    config.yaml    screens/` |
| `Attach Application` | Connects to already-running app | `Attach Application    1234` (process ID) |
| `Close Application` | Closes the app | `Close Application` |
| `Click Element` | Left-clicks an element | `Click Element    LOGIN.LOGIN_BUTTON` |
| `Double Click Element` | Double-clicks | `Double Click Element    FILES.FILE_ICON` |
| `Right Click Element` | Right-clicks (opens context menu) | `Right Click Element    FILES.FILE_ICON` |
| `Input Text` | Types text into a field | `Input Text    LOGIN.USERNAME_FIELD    john.doe` |
| `Send Keys` | Sends keyboard keys | `Send Keys    LOGIN.USERNAME_FIELD    {ENTER}` |
| `Clear Text` | Clears a text field | `Clear Text    SEARCH.SEARCH_BOX` |
| `Get Text` | Reads text from an element | `${value}=    Get Text    STATUS.STATUS_LABEL` |
| `Wait For Element` | Waits until element appears | `Wait For Element    CLAIMS.SAVE_BUTTON` |
| `Element Should Exist` | Fails if element is not there | `Element Should Exist    LOGIN.ERROR_MESSAGE` |
| `Element Should Be Visible` | Fails if element is hidden | `Element Should Be Visible    MAIN.MENU_BAR` |
| `Take Screenshot` | Saves a screenshot | `Take Screenshot    my_screenshot` |
| `Select Item` | Chooses an item from a dropdown | `Select Item    CLAIMS.STATUS_DROPDOWN    Active` |
| `Drag And Drop` | Drags one element onto another | `Drag And Drop    BOARD.ITEM_A    BOARD.ITEM_B` |
| `Switch Window` | Moves focus to a different window | `Switch Window    Save As` |
| `Maximize Window` | Maximises the app window | `Maximize Window` |
| `Minimize Window` | Minimises the app window | `Minimize Window` |
| `Scan Application Screen` | Scans the current screen and writes a `locators.yaml` | `Scan Application Screen    output_path=screens/login/locators.yaml` |
| `Get Healing Report` | Returns a summary of all self-heal events in this run | `${report}=    Get Healing Report` |

### Self-healing locators

The platform monitors every element lookup. When a primary locator fails but a fallback succeeds, it records a **soft heal** automatically — no test intervention needed. When all locators fail, three recovery strategies run in sequence before the step is marked as failed:

| Strategy | What it does |
|----------|-------------|
| **Popup dismissal** | Detects stray confirmation dialogs (Save, Error, Warning) and closes them, then retries the original step |
| **Stale window reattach** | Detects when the main window handle has become invalid, finds the new window, and retries |
| **Fuzzy name matching** | Finds an element with a similar (≥72% match) name when the exact name has changed slightly |

After a test run, call `Get Healing Report` to see a YAML summary of every heal event — useful for identifying locators that need updating.

```robotframework
*** Test Cases ***
My Test With Healing Report
    Launch Application
    ...
    ${report}=    Get Healing Report
    Log    ${report}
```

A `healing_report.yaml` is also written to the output directory automatically at the end of every suite.

### Real-world test example — Claims application

```robotframework
*** Settings ***
Library       desktop_automation_platform.robot_keywords.DesktopKeywords
Library       Collections
Suite Setup   Launch Application    config\claims.yaml    locators\claims.yaml
Suite Teardown    Close Application

*** Variables ***
${VALID_USER}      john.doe@company.com
${VALID_PASS}      Password123!
${CLAIM_AMOUNT}    1500.00

*** Test Cases ***
Login With Valid Credentials
    [Documentation]    Happy path login test
    Input Text          LOGIN_USERNAME    ${VALID_USER}
    Input Text          LOGIN_PASSWORD    ${VALID_PASS}
    Click Element       LOGIN_BUTTON
    Wait For Element    DASHBOARD_WELCOME_TEXT    timeout=20
    Element Should Exist    CLAIMS_MENU

Login With Invalid Password Shows Error
    [Documentation]    Verifies that wrong password shows an error message
    Input Text          LOGIN_USERNAME    ${VALID_USER}
    Input Text          LOGIN_PASSWORD    WrongPassword!
    Click Element       LOGIN_BUTTON
    Wait For Element    LOGIN_ERROR_MESSAGE
    ${error}=    Get Text    LOGIN_ERROR_MESSAGE
    Should Contain      ${error}    Invalid

Create New Claim
    [Documentation]    End-to-end claim creation
    # Login first
    Input Text          LOGIN_USERNAME    ${VALID_USER}
    Input Text          LOGIN_PASSWORD    ${VALID_PASS}
    Click Element       LOGIN_BUTTON
    Wait For Element    DASHBOARD_WELCOME_TEXT

    # Navigate to Claims
    Click Element       CLAIMS_MENU
    Wait For Element    CLAIMS_NEW_CLAIM_BUTTON
    Click Element       CLAIMS_NEW_CLAIM_BUTTON

    # Fill in the claim form
    Wait For Element    CLAIM_AMOUNT_FIELD
    Input Text          CLAIM_AMOUNT_FIELD      ${CLAIM_AMOUNT}
    Select Item         CLAIM_TYPE_DROPDOWN     Medical
    Input Text          CLAIM_NOTES             Routine checkup
    Click Element       CLAIM_SAVE_BUTTON

    # Verify claim was saved
    Wait For Element    CLAIM_SUCCESS_MESSAGE
    ${msg}=    Get Text    CLAIM_SUCCESS_MESSAGE
    Should Contain      ${msg}    saved successfully
```

### Organising tests into files

```
tests\
├── login\
│   ├── test_login_valid.robot
│   ├── test_login_invalid.robot
│   └── test_login_lockout.robot
├── claims\
│   ├── test_create_claim.robot
│   ├── test_edit_claim.robot
│   └── test_delete_claim.robot
└── reports\
    ├── test_generate_report.robot
    └── test_export_report.robot
```

---

## 10. Run your tests

### Activate the virtual environment first (always do this)

```powershell
cd "C:\Path\To\Desktop-Claude-Enterprise-Autoamtion-Framework"
.venv\Scripts\Activate.ps1
```

### Run all tests

```powershell
robot tests\
```

### Run a single test file

```powershell
robot tests\login\test_login_valid.robot
```

### Run a specific test case by name

```powershell
robot --test "Login With Valid Credentials" tests\
```

### Run tests with a tag

Add `[Tags]` to your test cases:
```robotframework
Create New Claim
    [Tags]    smoke    claims    regression
```

Then filter by tag:
```powershell
robot --include smoke tests\         # Run only smoke tests
robot --exclude regression tests\    # Skip regression tests
```

### Save output to a custom folder

```powershell
robot --outputdir my_results tests\
```

### Run with more detail in the log

```powershell
robot --loglevel DEBUG tests\
```

---

## 11. Understanding the reports

After every run, Robot Framework produces three files in your `reports\` folder:

| File | What it contains | When to open it |
|------|-----------------|-----------------|
| `report.html` | Summary — pass/fail count, test names, duration | Always |
| `log.html` | Full step-by-step execution log with screenshots | When a test fails |
| `output.xml` | Machine-readable results (for CI/CD tools) | For Azure DevOps / Jenkins |

**Open `reports\report.html` in any browser** — no special tools needed.

### Screenshot on failure

When a step fails, the framework automatically saves a screenshot to `reports\screenshots\` and embeds a link in the log. Click the link in `log.html` to see exactly what the screen looked like when the failure occurred.

---

## 12. Troubleshooting

### "AdapterInitializationException: clr is not installed" or "pythonnet not found"

This is the most common issue on a fresh machine. `pythonnet` is the Python–.NET bridge that FlaUI requires. Install it inside the virtual environment:

```powershell
# Make sure the venv is active first (you should see (.venv) in your prompt)
pip install pythonnet
```

Then retry `robot test_notepad.robot`. If pip fails to build it:
```powershell
pip install --upgrade pip wheel
pip install pythonnet
```

### "Resource file '...' does not exist" or "No keyword with name '...' found"

You are running the test from the wrong directory. Robot Framework resolves resource file paths relative to where you run the `robot` command. Always `cd` into the project folder first:

```powershell
cd my_first_test          # or your project folder
robot test_notepad.robot  # now the paths resolve correctly
```

Never run `robot` from the framework root when your test is inside `my_first_test\`.

### "FlaUI assemblies not found"

Run the FlaUI setup script again:
```powershell
.\scripts\setup_flaui.ps1
```

Or set the path manually:
```powershell
$env:FLAUI_PATH = "C:\Path\To\FlaUI\Dlls"
robot tests\
```

### "Element not found" — the test cannot find a button or field

1. Open **FlaUI Inspect** and hover over the element
2. Check that the `AutomationId` or `Name` in your `locators.yaml` matches exactly
3. Increase the timeout in your locator:
   ```yaml
   SLOW_LOADING_ELEMENT:
     primary:
       strategy: automation_id
       value: myElement
       timeout: 30      # Increase to 30 seconds
   ```
4. Add a fallback strategy:
   ```yaml
   MY_BUTTON:
     primary:
       strategy: automation_id
       value: btnOK
     fallbacks:
       - strategy: name
         value: OK
   ```

### "Application not launching" — the executable path is wrong

Make sure the path uses double backslashes or forward slashes:
```yaml
executable: C:\\Apps\\claims.exe     # Double backslash
# OR
executable: C:/Apps/claims.exe       # Forward slash (also works)
```

### Virtual environment not activating

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.venv\Scripts\Activate.ps1
```

### "Access denied" when automating a UAC-elevated application

Run your terminal **as Administrator**:
- Right-click PowerShell → "Run as Administrator"
- Navigate to your project folder
- Activate the virtual environment and run tests

### Tests are very slow

- Check that your app's main window is in the foreground (not minimised)
- Reduce `timeout` in `config.yaml` for elements that load quickly
- Set `logging_level: WARNING` instead of `INFO` to reduce log overhead

### Screenshot is blank / black

This happens when the app is behind another window. Add this to your test:
```robotframework
Maximize Window
Wait For Element    SOME_ELEMENT
Take Screenshot
```

---

## 13. FAQ

**Q: Do I need to know Python to use this?**
No. You write tests in Robot Framework which reads like plain English. You only need Python installed — you do not need to write Python code.

**Q: What if my app updates and the buttons move?**
Update the `locators.yaml` file with the new `AutomationId` or `Name` values. The framework uses fallback strategies, so if one breaks another may still work.

**Q: Can I run tests on a remote machine?**
Yes. Install the framework on the remote machine, copy your `config.yaml`, `locators.yaml`, and `.robot` files, then run `robot tests\` there. Results can be sent back to Azure DevOps or any CI system automatically.

**Q: Can I run multiple tests at the same time (in parallel)?**
Parallel execution requires one application instance per parallel worker. This is supported but requires additional configuration — ask the platform team for the `pabot` integration guide.

**Q: My app is Citrix/RDP — will image-based testing be slow?**
Image matching adds 0.5–2 seconds per action. For Citrix, this is unavoidable. To speed it up, increase the `similarity_threshold` closer to 1.0 to fail fast on wrong images.

**Q: How do I integrate with Azure DevOps?**
Add a pipeline step:
```yaml
- script: |
    .venv\Scripts\Activate.ps1
    robot --outputdir $(Build.ArtifactStagingDirectory)\reports tests\
  displayName: Run Desktop Automation Tests
- task: PublishTestResults@2
  inputs:
    testResultsFormat: 'JUnit'
    testResultsFiles: '**\output.xml'
```

**Q: The auto-detection chose the wrong adapter — how do I override it?**
Set `adapter_mode` explicitly in your `config.yaml`:
```yaml
framework:
  adapter_mode: flaui    # Force FlaUI regardless of what is detected
```

---

## Corporate IT Setup

If your machine is managed by IT and you cannot install software, share this checklist with your IT team:

| Software | Download from | Version needed |
|----------|--------------|----------------|
| Python | python.org | 3.10 or newer (64-bit) |
| .NET Runtime | dotnet.microsoft.com | 6.0 or newer |
| NuGet CLI | nuget.org/downloads | Latest |

After IT installs the above, run:
```powershell
.\scripts\install.ps1
```

No Administrator rights are needed for the Python packages — they install into the user's home directory.

---

## Platform Roadmap

| Phase | Status | What it includes |
|-------|--------|-----------------|
| Phase 1 | Complete | Framework architecture, interfaces, config, technology detection |
| Phase 2 | Complete | FlaUI adapter — WPF, WinForms, WinUI3, MAUI, Win32 |
| Phase 3 | Complete | Robot Framework keyword layer, three-tier Screen Object Model, libspec for IDE auto-complete |
| Phase 4 | Complete | Automatic locator scanner — `Scan Application Screen` keyword, YAML exporter, scored strategy selection |
| Phase 5 | Complete | Self-healing locators — popup dismissal, stale window reattach, fuzzy name matching, healing report |
| Phase 6 | Complete | All remaining adapters — pywinauto (Win32/Qt/MFC), WinAppDriver (UWP/WinUI3 via Appium), Java Access Bridge, Electron/Playwright, Sikuli image-based |

---

## Getting help

- **Something is broken**: Check [Section 12 — Troubleshooting](#12-troubleshooting) first
- **Element not found**: Use FlaUI Inspect to verify the `AutomationId`
- **New feature request**: Raise a ticket with the QA Platform Team
- **Adapter question**: Refer to [Section 6 — Which adapter should I use?](#6-which-adapter-should-i-use)
