# Getting Started with the Desktop Automation Platform

> **Who this guide is for:** Anyone joining a project that uses this framework — whether you are a
> business analyst writing your first test, a developer setting up the infrastructure, or a test lead
> onboarding a new application. No prior automation experience is required to follow this guide.

---

## Table of Contents

1. [What is this framework and why use it?](#1-what-is-this-framework-and-why-use-it)
2. [How does it work? The big picture](#2-how-does-it-work-the-big-picture)
3. [Before you start — what you need](#3-before-you-start--what-you-need)
4. [One-time setup — installing the platform](#4-one-time-setup--installing-the-platform)
5. [Starting a new automation project](#5-starting-a-new-automation-project)
6. [Step 1 — Tell the framework about your application](#6-step-1--tell-the-framework-about-your-application)
7. [Step 2 — Map your screen elements (locators)](#7-step-2--map-your-screen-elements-locators)
8. [Step 3 — Write screen keywords](#8-step-3--write-screen-keywords)
9. [Step 4 — Write business keywords](#9-step-4--write-business-keywords)
10. [Step 5 — Write your tests](#10-step-5--write-your-tests)
11. [Running your tests](#11-running-your-tests)
12. [Reading your results](#12-reading-your-results)
13. [When something breaks](#13-when-something-breaks)
14. [Frequently asked questions](#14-frequently-asked-questions)
15. [Quick reference card](#15-quick-reference-card)

---

## 1. What is this framework and why use it?

### The problem it solves

Testing a desktop application manually is slow, expensive, and error-prone. Every time the software changes, a human has to click through dozens of screens and check that everything still works. On big projects, this can take days — and still misses things.

This framework lets you **write those checks once as automated tests** that run in minutes, catch problems immediately, and never get tired or distracted.

### What makes this framework different

Most automation tools require you to write tests in a technical scripting language, mixing "find button by ID 42" with "verify the claim was approved" — which means only developers can write or read the tests.

This framework is built on a different idea:

> **Tests should read like requirements, not code.**

A test in this framework looks like this:

```
Open Claims Application
Submit A New Medical Claim    policy=POL-001    amount=£2,500
Verify Claim Status Is         Approved
```

A business analyst can read that and immediately understand what is being tested. A developer can read it and understand what needs to be automated. Both can work on the same project without getting in each other's way.

### Who can use it

| Role | What you do with it |
|---|---|
| **Business Analyst / Test Lead** | Write the test scenarios (Step 10). Describe what the system should do in plain English. |
| **Developer / Automation Engineer** | Build the screen and business keywords (Steps 3–4). Wire the plain-English tests to the actual application. |
| **Tech Lead / Architect** | Set up the project, configure the application, manage locators (Steps 1–2). |

---

## 2. How does it work? The big picture

Think of the framework like a **restaurant kitchen**:

```
┌─────────────────────────────────────────────────────────────────┐
│  CUSTOMER ORDER (Test File)                                     │
│  "I'd like the Eggs Benedict, please."                          │
│  The customer just describes WHAT they want — not how to cook.  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│  RECIPE (Business Keywords)                                     │
│  "Eggs Benedict" = Poach two eggs + Make hollandaise + Toast    │
│  muffins. Combines cooking steps into a named dish.             │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│  COOKING STEPS (Screen Keywords)                                │
│  "Poach an egg" = Boil water, add vinegar, crack egg gently...  │
│  One action, done correctly, on one part of the stove.          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│  KITCHEN EQUIPMENT (Platform + Locators)                        │
│  The actual tools: hob, whisk, pan. The framework knows how     │
│  to operate each piece of equipment on your specific stove.     │
└─────────────────────────────────────────────────────────────────┘
```

In software terms:

```
┌──────────────────────────────────────────────────────┐
│  tests/test_claims.robot                             │
│  "Submit Valid Medical Claim"                        │
│  Only business keywords — readable by anyone         │
└───────────────────────┬──────────────────────────────┘
                        │ calls
┌───────────────────────▼──────────────────────────────┐
│  resources/business_keywords.resource                │
│  "Submit A New Medical Claim"                        │
│  = Open Form + Enter Details + Click Submit          │
└───────────────────────┬──────────────────────────────┘
                        │ calls
┌───────────────────────▼──────────────────────────────┐
│  screens/claims_entry/keywords.resource              │
│  "Enter Policy Number", "Click Submit Button"        │
│  One action on one screen                            │
└───────────────────────┬──────────────────────────────┘
                        │ uses
┌───────────────────────▼──────────────────────────────┐
│  screens/claims_entry/locators.yaml                  │
│  POLICY_NUMBER_FIELD: automation_id=txtPolicy        │
│  The "address" of each button, field, and label      │
└──────────────────────────────────────────────────────┘
```

**The key benefit:** When your application's screen changes — say a button moves or a field gets renamed — you update **one locator file**, and every test that uses that button automatically works again. You never touch the test itself.

---

## 3. Before you start — what you need

### Software to install (one time per machine)

| What | Why | Where to get it |
|---|---|---|
| **Python 3.9 or later** | The framework runs on Python | python.org/downloads |
| **.NET 6+ SDK** | Required to communicate with Windows applications | dotnet.microsoft.com/download |
| **VS Code** (recommended) | Code editor with Robot Framework support | code.visualstudio.com |
| **Robot Framework Language Server** (VS Code extension) | Highlights and auto-completes Robot Framework tests | Search "Robot Framework" in VS Code Extensions |

### Check Python is installed

Open a terminal (press `Win + R`, type `powershell`, press Enter) and run:

```powershell
python --version
```

You should see something like `Python 3.11.4`. If you see an error, install Python first.

### Check .NET is installed

```powershell
dotnet --version
```

You should see `6.0.x` or higher. If not, install the .NET SDK.

---

## 4. One-time setup — installing the platform

This is done **once** when you first clone the repository on a new machine. Someone on your team (usually the tech lead) will also have done this when setting up the project.

### Step 1 — Get the code

```powershell
# Clone or download the framework to your machine
# (your tech lead will give you the exact repository URL)
git clone <repository-url>
cd Desktop-Claude-Enterprise-Automation-Framework
```

### Step 2 — Create a Python virtual environment

A virtual environment is like a clean room for your project's software — it keeps everything tidy and prevents conflicts with other tools on your machine.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

After activation, your terminal prompt will show `(.venv)` at the start. This means you are inside the clean room.

### Step 3 — Install Python packages

```powershell
pip install -e .
```

This installs the framework and all its dependencies. Takes about 2–3 minutes the first time.

### Step 4 — Install FlaUI (the Windows automation engine)

```powershell
.\scripts\setup_flaui.ps1
```

This downloads the components that allow the framework to "see" and "click" inside Windows applications. Takes about 1 minute.

### Step 5 — Verify everything works

```powershell
cd examples\notepad_reference
robot tests\test_notepad.robot
```

You should see Notepad open, some text get typed into it, and then Notepad close. The terminal should end with:
```
1 test, 1 passed, 0 failed
```

If you see this, the platform is working correctly. 

---

## 5. Starting a new automation project

When you start automating a **new application**, use the scaffolding tool. It creates the correct folder structure automatically — you never have to create files manually.

### Run the scaffolding tool

```powershell
python scripts\new_project.py `
    --name "Claims Desktop" `
    --executable "C:\Apps\Claims\ClaimsDesktop.exe" `
    --screens login claims_entry dashboard `
    --output C:\Projects\claims-automation
```

**What the options mean:**

| Option | What to put here |
|---|---|
| `--name` | The friendly name of the application you are automating |
| `--executable` | The full Windows path to the application's `.exe` file |
| `--screens` | The names of the main screens you will automate (one word each, use underscores) |
| `--output` | Where to create the project on your computer |

### What gets created

```
claims-automation/
│
├── config.yaml                          ← Your application settings
│
├── screens/
│   ├── login/
│   │   ├── locators.yaml               ← "Addresses" of elements on the Login screen
│   │   └── keywords.resource           ← Actions on the Login screen
│   ├── claims_entry/
│   │   ├── locators.yaml               ← "Addresses" of elements on Claims Entry
│   │   └── keywords.resource           ← Actions on Claims Entry
│   └── dashboard/
│       ├── locators.yaml
│       └── keywords.resource
│
├── resources/
│   ├── platform_settings.resource      ← Framework connection (do not edit)
│   └── business_keywords.resource      ← Your business workflows go here
│
└── tests/
    ├── test_login.robot                 ← Your test scenarios go here
    ├── test_claims_entry.robot
    └── test_dashboard.robot
```

> **Think of it like a filing cabinet.** Each screen gets its own drawer (`screens/login/`).
> Inside the drawer: a card index of element addresses (`locators.yaml`) and a list of
> things you can do on that screen (`keywords.resource`).

---

## 6. Step 1 — Tell the framework about your application

Open `config.yaml`. It was pre-filled by the scaffolding tool — just update the values:

```yaml
framework:
  adapter_mode: flaui          # flaui = standard .NET apps (WPF, WinForms, WinUI3)
                               # pywinauto = Win32, Qt, MFC, legacy apps
                               # winappdriver = UWP / Windows Store apps
                               # auto = platform detects the right adapter
  retry_count: 2               # How many times to retry if a click fails (2 is fine)
  screenshot_on_failure: true  # Take a screenshot when a test fails (leave on)
  logging_level: INFO

application:
  name: Claims Desktop                              # Friendly name (for reports)
  executable: C:\Apps\Claims\ClaimsDesktop.exe      # Full path to the .exe
  launch_timeout_seconds: 15                        # Seconds to wait for the app to open
```

**That's it for configuration.** The framework will read this file every time it runs.

> **Tip:** If your application takes a long time to start up (e.g., connects to a database on launch),
> increase `launch_timeout_seconds` to `30` or `60`.

---

## 7. Step 2 — Map your screen elements (locators)

A **locator** is the framework's way of finding a specific button, text field, or label on screen. Think of it like a postal address — the framework needs the address to know where to click.

### Option A — Auto-scan (recommended for new projects)

The easiest way to build your locator list is to let the framework scan your application automatically.

**Write a temporary test** in any `.robot` file:

```robotframework
*** Settings ***
Resource    resources/business_keywords.resource
Suite Teardown    Close Application

*** Test Cases ***
Scan The Login Screen
    Launch Application
    Scan Application Screen    output_path=screens/login/locators.yaml
```

Run it:
```powershell
robot tests\test_login.robot
```

The framework will:
1. Open your application
2. Walk through every button, field, and label it can find
3. Write them all to `screens/login/locators.yaml` with suggested names

Open the generated file — you will see something like:

```yaml
# Auto-generated by Desktop Automation Platform — Locator Scanner

BTN_LOGIN_BUTTON:
  primary:
    strategy: automation_id
    value: "btnLogin"
  fallback:
    - strategy: name
      value: "Login"
  metadata:
    description: Auto-generated — review and update this description. Score: 100/100.

TXT_USERNAME_FIELD:
  primary:
    strategy: automation_id
    value: "txtUsername"
  ...
```

**After scanning:**
1. Review the generated keys — rename them to something meaningful (`BTN_LOGIN_BUTTON` → `LOGIN_BUTTON`)
2. Delete elements you will never interact with in tests
3. Update the `description` in each `metadata` block to explain what the element is

### Option B — Add locators manually

If you prefer to add locators one at a time as you write tests, edit `screens/<screen>/locators.yaml` directly:

```yaml
# screens/login/locators.yaml

USERNAME_FIELD:
  primary:
    strategy: automation_id     # Best choice — stable developer-set ID
    value: "txtUsername"
  fallback:
    - strategy: name
      value: "Username"         # Used if automation_id is ever removed
  metadata:
    description: Username input field on the Login screen

PASSWORD_FIELD:
  primary:
    strategy: automation_id
    value: "txtPassword"
  fallback:
    - strategy: name
      value: "Password"
  metadata:
    description: Password input field on the Login screen

LOGIN_BUTTON:
  primary:
    strategy: automation_id
    value: "btnLogin"
  fallback:
    - strategy: name
      value: "Log In"
  metadata:
    description: Login submit button
```

### How to find the right identifier (for developers)

The best tool is **Accessibility Insights for Windows** (free from Microsoft). It shows you the `AutomationId`, `Name`, and `ControlType` of every element on screen.

1. Download from: `accessibilityinsights.io`
2. Open your application
3. Open Accessibility Insights → click "FastPass" or hover over elements
4. The properties panel shows you exactly what to put in your locator

**Identifier priority — always use the highest one available:**

| Priority | Strategy | What it is |
|---|---|---|
| 1st | `automation_id` | A permanent ID the developer set in code. Most stable. |
| 2nd | `name` | The label or caption visible on screen. |
| 3rd | `control_type` | The type of element (Button, Edit box, etc.). |
| 4th | `class_name` | The Windows class name (mainly for older apps). |

---

## 8. Step 3 — Write screen keywords

Screen keywords are the **individual actions** your tests can perform on a single screen. Each keyword does exactly one thing.

Open `screens/login/keywords.resource`. The scaffolding tool put example placeholders there — replace them with real actions for your screen:

```robotframework
*** Settings ***
Resource    ../../resources/platform_settings.resource

*** Keywords ***
Enter Username
    [Documentation]    Types the given username into the Username field.
    [Arguments]    ${username}
    Input Text    LOGIN.USERNAME_FIELD    ${username}

Enter Password
    [Documentation]    Types the given password into the Password field.
    [Arguments]    ${password}
    Input Text    LOGIN.PASSWORD_FIELD    ${password}

Click Login Button
    [Documentation]    Clicks the Login button to submit the credentials.
    Click    LOGIN.LOGIN_BUTTON

Read Login Error Message
    [Documentation]    Returns the text of the error message shown after a failed login.
    ${message}=    Get Text    LOGIN.ERROR_MESSAGE_LABEL
    RETURN    ${message}
```

> **Notice:** Each keyword name says exactly what it does. `Enter Username` enters a username.
> `Click Login Button` clicks the login button. No guessing needed.

> **Notice:** The locator names have `LOGIN.` in front — that is the screen namespace the framework
> adds automatically from the folder name. You always use `SCREENNAME.ELEMENT_KEY` when calling
> locators in keywords.

**The golden rule for screen keywords:**
- One action only. If a keyword does two things, split it.
- No business logic. No "if the user is locked, do this instead".
- No assertions. Screen keywords just *do* things. The caller decides what to check.

---

## 9. Step 4 — Write business keywords

Business keywords combine screen actions into **meaningful workflows** that match how a real user would complete a task.

Open `resources/business_keywords.resource`:

```robotframework
*** Settings ***
Resource    platform_settings.resource
Resource    ../screens/login/keywords.resource
Resource    ../screens/claims_entry/keywords.resource

*** Keywords ***
Log In As Claims Processor
    [Documentation]    Logs in to the application using claims processor credentials.
    ...                The application must already be launched before calling this keyword.
    [Arguments]    ${username}    ${password}
    Enter Username    ${username}
    Enter Password    ${password}
    Click Login Button

Submit A New Medical Claim
    [Documentation]    Completes the claims entry form for a medical claim and submits it.
    [Arguments]    ${policy_number}    ${amount}
    Open New Claim Form
    Select Claim Type       Medical
    Enter Policy Number     ${policy_number}
    Enter Claim Amount      ${amount}
    Click Submit Claim

Verify Claim Status Is
    [Documentation]    Checks that the claim status label shows the expected status.
    [Arguments]    ${expected_status}
    ${actual}=    Read Claim Status
    Should Contain    ${actual}    ${expected_status}
```

> **Business keywords are what a business analyst would write in a test plan:**
> "Log in as claims processor, submit a new medical claim for policy POL-001,
> verify the status is Approved." Those are your three keywords.

**The golden rule for business keywords:**
- Call screen keywords only — never call `Input Text`, `Click`, etc. directly.
- Name them from the user's perspective, not the system's: "Submit A New Claim" not "Fill Form And Press Button".
- One keyword per user goal.

---

## 10. Step 5 — Write your tests

This is where business analysts can contribute directly. Test files contain only business keyword calls — no technical details at all.

Open `tests/test_claims_entry.robot`:

```robotframework
*** Settings ***
Resource         ../resources/business_keywords.resource
Suite Teardown   Close Application

*** Test Cases ***
Submit Valid Medical Claim
    [Documentation]    A claims processor can submit a valid medical claim and
    ...                the system accepts it with status Approved.
    [Tags]    smoke    claims    regression
    Launch Application
    Log In As Claims Processor    processor1    Pass@word1
    Submit A New Medical Claim    POL-20240001    2500
    Verify Claim Status Is        Approved

Submit Claim Fails For Expired Policy
    [Documentation]    The system rejects claims submitted against an expired policy.
    [Tags]    regression    claims    negative
    Launch Application
    Log In As Claims Processor    processor1    Pass@word1
    Submit A New Medical Claim    POL-EXPIRED    1000
    Verify Claim Status Is        Policy Expired — Claim Rejected
```

**What each part means:**

| Section | Purpose |
|---|---|
| `*** Settings ***` | Loads your keyword files and defines what happens after all tests run |
| `Suite Teardown   Close Application` | Ensures the app closes even if a test fails — always include this |
| `*** Test Cases ***` | Each block under here is one test |
| `[Documentation]` | Plain English description of what this test proves |
| `[Tags]` | Labels for filtering — `smoke` tests run on every build, `regression` runs weekly |
| The keyword calls | What the test actually does — reads like a user story |

**Writing good test names:** Name the test after what it proves, not what it does.
- Good: `Submit Valid Medical Claim`
- Bad: `Fill In Form Click Submit Check Status`

---

## 11. Running your tests

### Run all tests

```powershell
# Navigate to your project folder first
cd C:\Projects\claims-automation

# Run everything
robot tests\
```

### Run just the smoke tests (fast, critical path only)

```powershell
robot --include smoke tests\
```

### Run tests for one screen

```powershell
robot tests\test_claims_entry.robot
```

### Run and save the report to a specific folder

```powershell
robot --outputdir reports tests\
```

### What you see while tests run

```
==============================================================================
Test Claims Entry
==============================================================================
Submit Valid Medical Claim                                            | PASS |
Submit Claim Fails For Expired Policy                                 | PASS |
------------------------------------------------------------------------------
Test Claims Entry                                             2 passed, 0 failed
==============================================================================
```

Green `PASS` means the test ran and the application behaved as expected.
Red `FAIL` means something did not work — check the report for details.

---

## 12. Reading your results

After every test run, three files appear in your project folder (or `reports/` if you used `--outputdir`):

| File | What it is |
|---|---|
| `report.html` | **Start here.** A colour-coded dashboard showing what passed and what failed. Open this in any browser. |
| `log.html` | Detailed step-by-step log of every action taken. Open this to understand *why* something failed. |
| `output.xml` | Machine-readable results used by CI/CD pipelines (Jenkins, Azure DevOps, etc.). You rarely need to open this directly. |

### How to read a failure

1. Open `report.html` — find the red test
2. Click on the test name
3. Look at the last few steps — the failed step is highlighted in red
4. The error message tells you what was expected vs what was found
5. If there is a screenshot attached, open it — it shows exactly what the screen looked like when the test failed

**Common failure messages and what they mean:**

| Message | What it likely means |
|---|---|
| `Locator 'LOGIN.SUBMIT_BUTTON' not found` | The button ID changed or the screen layout changed. Update your locators. |
| `Should Contain 'Approved' but got 'Pending'` | The application returned a different result than expected. This is a real bug — raise it. |
| `ApplicationLaunchException` | The application did not start in time. Check it is installed and the path in `config.yaml` is correct. |
| `Element not visible within timeout` | The screen took too long to load. Try increasing `launch_timeout_seconds` in `config.yaml`. |

---

## 12a. Self-healing — what happens when a locator fails

The platform tries to fix itself before failing a test. You do not write any recovery code — it runs automatically in the background.

**What it does:**

| Situation | What the platform does |
|---|---|
| Primary locator fails but a fallback is defined | Tries each fallback in order. First one that works is used. |
| An unexpected dialog appears (Save / Error / Warning) | Dismisses the dialog automatically and retries the original step. |
| The application window refreshed or a modal closed | Finds the new window handle and retries the step. |
| A button label changed slightly (e.g., "Save" → "Save File") | Finds the closest-matching element (≥72% similarity) and uses it. |

**How to see what was healed:**

After a test run, a `healing_report.yaml` is written automatically. You can also read it in a test:

```robotframework
*** Test Cases ***
My Test
    Launch Application
    ...any keywords...
    ${report}=    Get Healing Report
    Log    ${report}
```

**What to do with the report:** If the same locator is healed on every run, update its `locators.yaml` entry permanently. Repeated healing means the original identifier has changed and the locator is now out of date.

---

## 13. When something breaks

### The application changed — tests are failing on locators

**Symptom:** `Locator 'CLAIMS_ENTRY.POLICY_NUMBER_FIELD' not found`

**Fix:** The element's identifier changed in the new version. Re-scan the screen:

```robotframework
Launch Application
Log In As Claims Processor    processor1    Pass@word1
Scan Application Screen    output_path=screens/claims_entry/locators_new.yaml
```

Open `locators_new.yaml`, find the element, copy its new identifier into your existing `locators.yaml`, and delete `locators_new.yaml`. Run the tests again.

---

### A test fails intermittently (sometimes passes, sometimes fails)

**Symptom:** The test passes when run manually but fails in the CI pipeline.

**Likely causes:**
- The screen takes longer to load in the pipeline environment → increase `launch_timeout_seconds`
- A previous test left the application in a bad state → check that `Suite Teardown   Close Application` is in every test file

---

### The application launches but the test cannot find any elements

**Symptom:** Everything starts up, but `Locator ... not found` errors appear immediately.

**Check:**
1. Is the application fully loaded? Some apps have a loading screen — the test may need a `Wait For Element` call before interacting.
2. Are you on Windows 11? Some applications expose elements differently on Windows 11 vs Windows 10. Re-scan to get the correct identifiers.

---

### Nothing works at all — framework errors on startup

**Symptom:** The test fails before even launching the application, with a long Python error.

**Fix checklist:**
1. Is the virtual environment activated? Your prompt should show `(.venv)`.
2. Did you run `.\scripts\setup_flaui.ps1`? Run it again if unsure.
3. Is .NET installed? Run `dotnet --version` — you need 6.0 or later.

If none of these help, contact your tech lead with the full error message from `log.html`.

---

## 14. Frequently asked questions

**Q: Do I need to know how to code to write tests?**

For writing test cases (Step 10), no. Test files read like plain English and follow a simple pattern. For writing screen and business keywords (Steps 8–9), basic familiarity with Robot Framework syntax is helpful but the learning curve is shallow — most of it is indentation and calling pre-built functions.

---

**Q: Can we automate any Windows application?**

Yes. The platform covers the full spectrum of Windows desktop applications:

| Application type | Adapter |
|---|---|
| WPF, WinForms, WinUI3, MAUI | FlaUI (default, UIA-based) |
| UWP / Windows Store apps | WinAppDriver (Appium protocol) |
| Win32, Qt, MFC, legacy VB6/Delphi | pywinauto |
| Java Swing / AWT | Java Access Bridge |
| Electron (VS Code, Slack, Teams) | Playwright |
| Citrix / RDP (no accessibility tree) | Sikuli (image-based) |

Set `adapter_mode: auto` and the platform detects the right adapter. Override with the specific adapter name if auto-detection picks the wrong one.

---

**Q: What happens if the application is updated and elements change?**

Only the `locators.yaml` file for that screen needs updating. Tests and keywords are written against locator names (`LOGIN.SUBMIT_BUTTON`), not against raw identifiers — so when the underlying ID changes, you fix it in one place and everything works again. The scanner (Step 7, Option A) makes this fast.

---

**Q: Can we run these tests in our CI/CD pipeline (Jenkins / Azure DevOps)?**

Yes. The framework produces a standard `output.xml` that Jenkins and Azure DevOps can read natively. Add a step to your pipeline:

```yaml
# Azure DevOps example
- script: |
    .venv\Scripts\Activate.ps1
    robot --outputdir reports tests\
  displayName: 'Run Automation Tests'

- task: PublishTestResults@2
  inputs:
    testResultsFormat: 'JUnit'
    testResultsFiles: 'reports/output.xml'
```

---

**Q: How many screens should each project cover?**

Automate the screens that are part of your critical business workflows first — login, the main data entry form, the results/status screen. Once those are stable, expand to edge cases and secondary screens. Start small and grow the suite over time.

---

**Q: Can two teams work on the same project at the same time?**

Yes. Because each screen has its own folder (`screens/<screen>/`), two people can work on different screens without conflicting. Use standard Git branching — one branch per feature or screen being automated.

---

**Q: Where do I put test data (usernames, policy numbers, etc.)?**

Pass them as keyword arguments as shown in the examples. For large datasets, Robot Framework supports data-driven tests using CSV or Excel files. Ask your tech lead to set this up.

---

## 15. Quick reference card

### Project setup — one-time

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
.\scripts\setup_flaui.ps1
```

### Create a new project

```powershell
python scripts\new_project.py `
    --name "My App" `
    --executable "C:\Apps\MyApp\MyApp.exe" `
    --screens login main_screen report `
    --output C:\Projects\my-app-automation
```

### Auto-scan a screen for locators

```robotframework
Launch Application
Scan Application Screen    output_path=screens/main_screen/locators.yaml
```

### Check for self-healed locators after a run

```robotframework
${report}=    Get Healing Report
Log    ${report}
```

Or open `healing_report.yaml` in the output directory directly.

### Run tests

```powershell
robot tests\                          # All tests
robot --include smoke tests\          # Smoke tests only
robot --include regression tests\     # Regression only
robot tests\test_login.robot          # One file
```

### File editing cheat sheet

| I want to... | Edit this file |
|---|---|
| Change the application path or settings | `config.yaml` |
| Add or fix an element identifier | `screens/<screen>/locators.yaml` |
| Add a new screen action | `screens/<screen>/keywords.resource` |
| Add a new business workflow | `resources/business_keywords.resource` |
| Add a new test scenario | `tests/test_<feature>.robot` |

### Locator identifier priority

```
1. automation_id   — developer-set ID, most reliable
2. name            — visible label or button text
3. class_name      — Windows class name (older apps)
4. control_type    — element type (Button, Edit, etc.)
```

### Tag your tests

```robotframework
[Tags]    smoke           # Critical — run on every build
[Tags]    regression      # Full suite — run nightly or weekly
[Tags]    <screen_name>   # Feature area — run when that area changes
[Tags]    wip             # Not ready — skip in CI pipeline
```

---

*For deeper technical details, see the [Style Guide](STYLE_GUIDE.md).*
*For a working example to study, see [examples/notepad_reference/](../examples/notepad_reference/).*
*For a scaffolded multi-screen example, see [examples/claims_reference/](../examples/claims_reference/).*
