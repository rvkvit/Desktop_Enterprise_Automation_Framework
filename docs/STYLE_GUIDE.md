# Desktop Automation Platform — Style Guide

> **Audience:** QA engineers and automation leads adopting this framework on their projects.
> This guide defines the conventions, patterns, and rules you must follow so that all projects
> built on this platform are consistent, maintainable, and easy to onboard.

---

## Table of Contents

1. [Core Philosophy](#1-core-philosophy)
2. [Standard Project Layout](#2-standard-project-layout)
3. [Three-Tier Keyword Architecture](#3-three-tier-keyword-architecture)
4. [Screen Object Model (SOM)](#4-screen-object-model-som)
5. [Locator Conventions](#5-locator-conventions)
6. [Configuration Conventions](#6-configuration-conventions)
7. [Naming Conventions](#7-naming-conventions)
8. [Keyword Authoring Rules](#8-keyword-authoring-rules)
9. [Anti-Patterns](#9-anti-patterns)
10. [Quick Reference Card](#10-quick-reference-card)

---

## 1. Core Philosophy

The platform is built on three principles. Every decision in this guide flows from them.

| Principle | What It Means |
|---|---|
| **Test files tell a story** | A test case should read like a business requirement, not an automation script. A non-technical stakeholder should understand what the test does by reading it. |
| **Change in one place** | When a screen changes, only the screen's own files change — not the tests that use it. |
| **Locators are configuration, not code** | No element identifiers live inside `.robot` or `.resource` keyword files. All locators live in `locators.yaml` files. |

---

## 2. Standard Project Layout

Every project using this platform must follow this directory structure.

```
my_project/
│
├── config.yaml                          # Application + framework settings
│
├── screens/                             # Screen Object Model — one folder per screen
│   ├── login/
│   │   ├── locators.yaml
│   │   └── keywords.resource
│   ├── claims_entry/
│   │   ├── locators.yaml
│   │   └── keywords.resource
│   └── dashboard/
│       ├── locators.yaml
│       └── keywords.resource
│
├── resources/
│   ├── platform_settings.resource       # Library import — the ONLY place it appears
│   └── business_keywords.resource       # Business-level keyword definitions
│
├── tests/
│   ├── test_login.robot
│   ├── test_claims_entry.robot
│   └── test_dashboard.robot
│
└── reports/                             # Generated — do not commit
    ├── output.xml
    ├── log.html
    └── screenshots/
```

### Rules

- `screens/` contains one subfolder per logical screen or dialog. Never share a locators file across two screens.
- `resources/platform_settings.resource` is the **single** place where `DesktopAutomationLibrary` is imported.
- `tests/` contains only `.robot` files. No `.resource` files belong here.
- `reports/` is generated at runtime. Add it to `.gitignore`.

---

## 3. Three-Tier Keyword Architecture

All automation is organised into exactly three tiers. Each tier has a strict responsibility. Crossing a tier is a defect in the automation code.

```
┌─────────────────────────────────────────────────────────────┐
│  TIER 3 — TEST FILES (.robot)                               │
│  Business language. What is being tested.                   │
│  e.g. "Submit Valid Claim"  "Verify Login Fails For Locked  │
│         User"                                               │
└────────────────────┬────────────────────────────────────────┘
                     │ calls
┌────────────────────▼────────────────────────────────────────┐
│  TIER 2 — BUSINESS KEYWORDS (resources/business_keywords)   │
│  Business workflows composed from screen actions.           │
│  e.g. "Log In As Claims Processor"  "Open New Claim Form"   │
└────────────────────┬────────────────────────────────────────┘
                     │ calls
┌────────────────────▼────────────────────────────────────────┐
│  TIER 1 — SCREEN KEYWORDS (screens/<name>/keywords.resource) │
│  Atomic actions on a single screen.                         │
│  e.g. "Enter Username"  "Click Submit Button"               │
│       "Read Status Label"                                   │
└────────────────────┬────────────────────────────────────────┘
                     │ calls
┌────────────────────▼────────────────────────────────────────┐
│  PLATFORM — DesktopAutomationLibrary                        │
│  Technology-agnostic primitives.                            │
│  Input Text, Click, Get Text, Element Exists, etc.          │
└─────────────────────────────────────────────────────────────┘
```

### What belongs at each tier

| Tier | Allowed | Forbidden |
|---|---|---|
| **Test file** | Business keyword calls, Robot built-ins (`Should Contain`, `Should Be Equal`, `Log`), tags, documentation | Platform keyword calls, locator names, any `${selector}` variable |
| **Business keywords** | Calls to screen keywords, calls to other business keywords, simple control flow (`Run Keyword If`) | Direct platform keyword calls (`Input Text`, `Click`), locator names |
| **Screen keywords** | Platform keyword calls, locator name constants (`SCREEN.ELEMENT`), screen-local variables | Business logic, assertions (`Should Contain`), calls to other screen's keywords |

---

## 4. Screen Object Model (SOM)

A **Screen** is any distinct UI surface your tests interact with: a window, a tab, a modal dialog, or a major panel with its own set of controls.

### One screen = one folder

```
screens/
└── claims_entry/
    ├── locators.yaml        ← element definitions for this screen
    └── keywords.resource    ← actions available on this screen
```

### Locator namespacing

When `DesktopAutomationLibrary` loads the `screens/` directory, it automatically prefixes every key with the folder name (uppercased):

```
screens/claims_entry/locators.yaml  →  CLAIMS_ENTRY.POLICY_NUMBER_FIELD
screens/login/locators.yaml         →  LOGIN.USERNAME_FIELD
```

This means:
- Locator keys in `locators.yaml` are written **without** the namespace prefix
- Locator keys in `keywords.resource` are always written **with** the namespace prefix
- No two screens can define a key with the same name — but if they do, the namespace prevents collisions

### Example — claims_entry screen

**`screens/claims_entry/locators.yaml`**
```yaml
POLICY_NUMBER_FIELD:
  primary:
    strategy: automation_id
    value: "txtPolicyNumber"
  fallback:
    - strategy: name
      value: "Policy Number"
  metadata:
    description: Policy number input on the Claims Entry form

CLAIM_TYPE_DROPDOWN:
  primary:
    strategy: automation_id
    value: "cboClaimType"
  metadata:
    description: Claim type selection dropdown

SUBMIT_BUTTON:
  primary:
    strategy: automation_id
    value: "btnSubmit"
  fallback:
    - strategy: name
      value: "Submit"
  metadata:
    description: Submits the claim form
```

**`screens/claims_entry/keywords.resource`**
```robotframework
*** Settings ***
Resource    ../../resources/platform_settings.resource

*** Keywords ***
Enter Policy Number
    [Arguments]    ${policy_number}
    Input Text    CLAIMS_ENTRY.POLICY_NUMBER_FIELD    ${policy_number}

Select Claim Type
    [Arguments]    ${claim_type}
    Select Item    CLAIMS_ENTRY.CLAIM_TYPE_DROPDOWN    ${claim_type}

Click Submit
    Click    CLAIMS_ENTRY.SUBMIT_BUTTON

```

**`resources/business_keywords.resource`**
```robotframework
*** Settings ***
Resource    platform_settings.resource
Resource    ../screens/login/keywords.resource
Resource    ../screens/claims_entry/keywords.resource

*** Keywords ***
Submit A New Claim
    [Arguments]    ${policy_number}    ${claim_type}
    Enter Policy Number    ${policy_number}
    Select Claim Type      ${claim_type}
    Click Submit
```

**`tests/test_claims_entry.robot`**
```robotframework
*** Settings ***
Resource         ../resources/business_keywords.resource
Suite Teardown   Close Application

*** Test Cases ***
Submit Valid Medical Claim
    [Tags]    smoke    claims
    Launch Application
    Submit A New Claim    POL-20240001    Medical
    Verify Claim Was Accepted
```

---

## 5. Locator Conventions

### Strategy selection — priority order

Always use the highest-priority strategy that is stable. Fall back only when necessary.

| Priority | Strategy | Use when |
|---|---|---|
| 1 | `automation_id` | The developer has set an AutomationId/AccessibilityId. Always prefer this — it survives UI reshuffles. |
| 2 | `name` | The control has a stable accessible name (label text, button caption). |
| 3 | `control_type` | No ID or name, but control type is unique enough in context (e.g. only one `Document` on the screen). |
| 4 | `class_name` | Win32/legacy apps where class names are stable. |
| 5 | `xpath` | Last resort for WPF/WinForms when nothing else uniquely identifies the element. |
| 6 | `image` | Only for apps with no accessibility tree (Citrix, legacy VB6, etc.). |

### Always provide at least one fallback

```yaml
# Good — primary will be tried first, fallback protects against renames
SUBMIT_BUTTON:
  primary:
    strategy: automation_id
    value: "btnSubmit"
  fallback:
    - strategy: name
      value: "Submit"

# Bad — single point of failure
SUBMIT_BUTTON:
  primary:
    strategy: automation_id
    value: "btnSubmit"
```

### Timeouts

Do not set a custom timeout unless you have a specific reason. The framework default (from `config.yaml`) applies automatically.

Only set explicit timeouts on elements that are known to load slowly:

```yaml
REPORT_TABLE:
  primary:
    strategy: automation_id
    value: "dgvReportResults"
    timeout: 30          # report data takes up to 30s to populate
  metadata:
    description: Report results grid — slow to load after search
```

### Generating locators automatically

Use the built-in scanner to bootstrap a screen's `locators.yaml` in seconds:

```robotframework
Launch Application
Scan Application Screen    output_path=screens/my_screen/locators.yaml
```

The scanner scores every element (`automation_id` = 100, `name` = 70, `control_type` = 20, `class_name` = 40), writes the highest-scoring strategy as the primary, and adds fallbacks automatically. Generated keys are in `UPPER_SNAKE_CASE`.

After scanning: review the file, rename keys to match your convention, delete elements you will not use, and update each `metadata.description`.

### Metadata

Always fill in `metadata.description`. It is the only documentation for why a locator exists and how it was identified.

```yaml
metadata:
  description: Main text editing area — Win11 uses Document control, Win10 uses Edit
```

### Key naming

- `UPPER_SNAKE_CASE` always
- Name the element by what it **is**, not where it **is**: `SAVE_BUTTON` not `BOTTOM_RIGHT_BUTTON`
- Be specific: `POLICY_NUMBER_FIELD` not `INPUT_FIELD_1`

---

## 6. Configuration Conventions

### One `config.yaml` per project

Every test project has exactly one `config.yaml` at its root. It is not shared across projects.

### Standard structure

```yaml
framework:
  adapter_mode: flaui            # flaui | winappdriver | pywinauto |
                                 # electron_playwright | java_access_bridge |
                                 # sikuli_image | auto
  retry_count: 2                 # number of automatic retries on element action failure
  screenshot_on_failure: true    # capture screenshot on any test failure
  logging_level: INFO            # DEBUG | INFO | WARNING

application:
  name: Claims Desktop           # human-readable name used in logs and reports
  executable: C:\Apps\Claims\ClaimsDesktop.exe
  launch_timeout_seconds: 15
  window_title: Claims Management System   # optional — used to find the main window
  working_directory: C:\Apps\Claims        # optional
  launch_arguments:                        # optional
    - "--env=UAT"
  environment:                             # optional env vars injected at launch
    CLAIMS_DB_HOST: "${CLAIMS_DB_HOST}"    # reference OS env var with ${VAR}
```

### Environment-specific values

Never hardcode environment-specific values (hostnames, connection strings, credentials) in `config.yaml`. Use OS environment variable references:

```yaml
# Good
application:
  environment:
    API_ENDPOINT: "${API_ENDPOINT}"

# Bad
application:
  environment:
    API_ENDPOINT: "https://claims-uat.internal.company.com"
```

### Do not store these in config

- Usernames or passwords (use a secrets manager or CI environment variables)
- Process IDs (PIDs change every launch)
- Absolute paths to test data (use `${CURDIR}` in Robot files)

---

## 7. Naming Conventions

### Files and directories

| Item | Convention | Example |
|---|---|---|
| Screen directory | `lower_snake_case` | `claims_entry`, `login`, `policy_dashboard` |
| Locator file | always `locators.yaml` | `screens/login/locators.yaml` |
| Screen keywords | always `keywords.resource` | `screens/login/keywords.resource` |
| Business keywords | `<domain>_keywords.resource` | `claims_keywords.resource` |
| Platform settings | always `platform_settings.resource` | `resources/platform_settings.resource` |
| Test files | `test_<feature>.robot` | `test_login.robot`, `test_claims_entry.robot` |
| Config | always `config.yaml` | `config.yaml` |

### Locator keys

| Convention | Example |
|---|---|
| `UPPER_SNAKE_CASE` | `POLICY_NUMBER_FIELD`, `SUBMIT_BUTTON` |
| Named for what it is, not where it sits | `SAVE_BUTTON` not `BOTTOM_BUTTON` |
| Specific, not generic | `USERNAME_FIELD` not `FIELD_1` |
| In code, always prefixed with namespace | `LOGIN.USERNAME_FIELD` |

### Robot keywords

| Tier | Pattern | Examples |
|---|---|---|
| **Screen keywords** | `Verb + Element` | `Enter Username`, `Click Login Button`, `Read Error Message` |
| **Business keywords** | `Verb + Business Concept` | `Log In As Claims Processor`, `Open New Claim Form`, `Verify Claim Was Rejected` |
| **Test case names** | `<Scenario being tested>` | `Submit Valid Medical Claim`, `Login Fails For Locked Account` |

### Variables

| Variable type | Convention | Example |
|---|---|---|
| Scalar | `${CamelCase}` | `${PolicyNumber}`, `${ClaimType}` |
| List | `@{CamelCase}` | `@{ClaimRows}` |
| Dict | `&{CamelCase}` | `&{ClaimData}` |

---

## 8. Keyword Authoring Rules

### Screen keywords must be atomic

Each screen keyword does exactly one thing. It does not chain multiple actions unless those actions are inseparable (e.g., typing text and pressing Tab to trigger validation).

```robotframework
# Good — one action per keyword
Enter Policy Number
    [Arguments]    ${policy_number}
    Input Text    CLAIMS_ENTRY.POLICY_NUMBER_FIELD    ${policy_number}

# Bad — chaining unrelated actions
Fill In Claim Form And Submit
    [Arguments]    ${policy_number}    ${claim_type}
    Input Text    CLAIMS_ENTRY.POLICY_NUMBER_FIELD    ${policy_number}
    Select Item   CLAIMS_ENTRY.CLAIM_TYPE_DROPDOWN    ${claim_type}
    Click         CLAIMS_ENTRY.SUBMIT_BUTTON
```

The second example belongs in a **business keyword**, not a screen keyword.

### Business keywords describe workflows, not steps

```robotframework
# Good — describes the what, not the how
Submit A New Claim
    [Arguments]    ${policy_number}    ${claim_type}
    Enter Policy Number    ${policy_number}
    Select Claim Type      ${claim_type}
    Click Submit

# Bad — describes the how (this is a screen keyword doing business-keyword work)
Submit A New Claim
    [Arguments]    ${policy_number}    ${claim_type}
    Input Text    CLAIMS_ENTRY.POLICY_NUMBER_FIELD    ${policy_number}
    Select Item   CLAIMS_ENTRY.CLAIM_TYPE_DROPDOWN    ${claim_type}
    Click         CLAIMS_ENTRY.SUBMIT_BUTTON
```

### Test cases must read as requirements

```robotframework
# Good — reads like a test scenario from a requirements doc
Submit Valid Medical Claim
    Launch Application
    Log In As Claims Processor
    Submit A New Claim    POL-20240001    Medical
    Verify Claim Was Accepted

# Bad — reads like an automation script, not a requirement
Submit Valid Medical Claim
    Launch Application
    Input Text    LOGIN.USERNAME_FIELD    processor1
    Input Text    LOGIN.PASSWORD_FIELD    pass123
    Click    LOGIN.LOGIN_BUTTON
    Input Text    CLAIMS_ENTRY.POLICY_NUMBER_FIELD    POL-20240001
    Select Item   CLAIMS_ENTRY.CLAIM_TYPE_DROPDOWN    Medical
    Click         CLAIMS_ENTRY.SUBMIT_BUTTON
```

### Always document keywords

Every keyword must have a `[Documentation]` tag that states **what** it does and any non-obvious **preconditions**:

```robotframework
Log In As Claims Processor
    [Documentation]    Logs in using the default claims processor credentials.
    ...                Requires the login screen to be visible (application must be launched first).
    [Arguments]    ${username}=${DEFAULT_PROCESSOR_USER}    ${password}=${DEFAULT_PROCESSOR_PASS}
    Enter Username    ${username}
    Enter Password    ${password}
    Click Login Button
```

### Tag your tests

Every test case must have at minimum one functional tag and one priority tag:

```robotframework
Submit Valid Medical Claim
    [Tags]    claims    smoke
    ...

Login Fails For Locked Account
    [Tags]    login    regression
```

Standard tag vocabulary:

| Tag | Meaning |
|---|---|
| `smoke` | Critical path — run on every build |
| `regression` | Full regression suite |
| `claims` / `login` / `dashboard` | Feature area |
| `wip` | Work in progress — skip in CI |
| `manual` | Documented but not automatable |

---

## 9. Anti-Patterns

These are the most common mistakes teams make. Treat violations as code review blockers.

### AP-1: Importing the library in test files

```robotframework
# WRONG — library is imported directly in the test file
*** Settings ***
Library    DesktopAutomationLibrary    config_path=config.yaml    locator_path=screens/
```

```robotframework
# CORRECT — test file imports only its resource files
*** Settings ***
Resource    resources/business_keywords.resource
Suite Teardown    Close Application
```

The library must only be imported in `resources/platform_settings.resource`.

---

### AP-2: Locator names in test files or business keywords

```robotframework
# WRONG — locator name leaking into a business keyword
Submit A New Claim
    [Arguments]    ${policy_number}
    Input Text    CLAIMS_ENTRY.POLICY_NUMBER_FIELD    ${policy_number}
```

```robotframework
# CORRECT — business keyword calls a screen keyword
Submit A New Claim
    [Arguments]    ${policy_number}
    Enter Policy Number    ${policy_number}
```

---

### AP-3: Putting locators in the wrong YAML file

```yaml
# WRONG — LOGIN.USERNAME_FIELD defined inside claims_entry/locators.yaml
USERNAME_FIELD:
  primary:
    strategy: automation_id
    value: "txtUsername"
```

Each screen's `locators.yaml` must only contain locators **for that screen**. The namespace is derived from the folder name — a login locator inside `claims_entry/` will be accessed as `CLAIMS_ENTRY.USERNAME_FIELD`, which is wrong.

---

### AP-4: Hardcoded waits

```robotframework
# WRONG
Sleep    5s
Click    DASHBOARD.REFRESH_BUTTON

# CORRECT — use explicit wait that fails fast when ready
Wait For Element    DASHBOARD.DATA_TABLE    timeout=30
Click    DASHBOARD.REFRESH_BUTTON
```

---

### AP-5: Asserting inside screen keywords

```robotframework
# WRONG — assertion inside a screen keyword
Read Status Label
    ${text}=    Get Text    CLAIMS_ENTRY.STATUS_LABEL
    Should Contain    ${text}    Approved     ← this is business logic

# CORRECT — screen keyword returns the value; caller asserts
Read Status Label
    ${text}=    Get Text    CLAIMS_ENTRY.STATUS_LABEL
    RETURN    ${text}
```

Assertions belong in business keywords or test cases.

---

### AP-6: One locators.yaml for the whole project

```
# WRONG — all locators in one file at project root
my_project/
└── locators.yaml    ← all 80 elements from 6 screens in one file
```

```
# CORRECT — one locators.yaml per screen
my_project/
└── screens/
    ├── login/locators.yaml
    ├── claims_entry/locators.yaml
    └── dashboard/locators.yaml
```

---

### AP-7: Skipping the fallback strategy

```yaml
# WRONG — single locator with no fallback
SAVE_BUTTON:
  primary:
    strategy: name
    value: "Save"
```

```yaml
# CORRECT — primary + at least one fallback
SAVE_BUTTON:
  primary:
    strategy: automation_id
    value: "btnSave"
  fallback:
    - strategy: name
      value: "Save"
```

---

## 10. Quick Reference Card

### Cheat sheet — which file does what

| I want to... | Edit this file |
|---|---|
| Add/change a UI element identifier | `screens/<screen>/locators.yaml` |
| Add a new action on a screen | `screens/<screen>/keywords.resource` |
| Add a new business workflow | `resources/business_keywords.resource` |
| Add a new test scenario | `tests/test_<feature>.robot` |
| Change the application under test | `config.yaml` |
| Change retry count / screenshot settings | `config.yaml` |
| Add a new screen to automate | Create `screens/<new_screen>/` with `locators.yaml` + `keywords.resource` |

### Locator strategy cheat sheet

```
stable AutomationId available?   → automation_id   (always preferred)
stable accessible Name?          → name
unique control type on screen?   → control_type
stable Win32 class name?         → class_name
nothing else works (WPF grid)?   → xpath
no accessibility tree (Citrix)?  → image
```

### Platform keywords quick reference

| Keyword | When to use |
|---|---|
| `Launch Application` | Suite Setup — opens the application |
| `Close Application` | Suite Teardown — always pair with Launch |
| `Click Element` | Clicking any control |
| `Input Text` | Typing into a text field |
| `Get Text` | Reading a label or field value |
| `Wait For Element` | Waiting for slow-loading elements |
| `Scan Application Screen` | Bootstrapping a new `locators.yaml` (one-time use) |
| `Get Healing Report` | After a suite run — shows which locators were auto-healed |

### Self-healing behaviour

The platform heals silently. You do not need to write any recovery code. If a primary locator fails:

1. **Fallback chain** — the next strategy in the locator's `fallback` list is tried automatically.
2. **Popup dismissal** — unexpected dialogs are closed and the action is retried.
3. **Stale window reattach** — if the window handle changes (modal closed, app restarted), a new handle is obtained.
4. **Fuzzy name match** — if a button text changed slightly (e.g., "Save" → "Save Document"), the closest match (≥72% similarity) is used.

Call `Get Healing Report` at the end of a suite to see a YAML summary of every heal event. Repeated heals on the same locator signal that it needs to be updated permanently.

### New project setup steps

```
# Option A — use the scaffolding tool (recommended)
python scripts/new_project.py \
    --name "My App" \
    --executable "C:\Apps\MyApp.exe" \
    --screens login main_screen report \
    --output C:\Projects\my-app-automation

# Option B — manual
1. Create the directory structure shown in Section 2
2. Update config.yaml with your application details
3. Run Scan Application Screen for each screen to bootstrap locators.yaml
4. Edit screens/<screen>/keywords.resource for each screen
5. Write business keywords in resources/business_keywords.resource
6. Write test cases in tests/test_<feature>.robot — business keywords only
7. Run: robot tests/
```

---

*This guide is maintained alongside the platform. When platform behaviour changes, update this document in the same pull request.*
