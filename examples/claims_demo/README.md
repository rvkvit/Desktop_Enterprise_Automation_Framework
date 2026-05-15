# Claims Desktop — Demo Test Project

A complete, ready-to-run example showing how to use the Desktop Automation Platform
to test a real desktop application end-to-end.

---

## What's in This Folder

```
claims_demo/
├── config.yaml                        ← Platform & app settings
├── locators.yaml                      ← Symbolic element names (edit these to match your app)
├── run_tests.ps1                      ← One-click test runner
└── tests/
    ├── login_tests.robot              ← Login / authentication tests
    ├── claim_submission_tests.robot   ← Submit and search for claims
    └── supervisor_workflow_tests.robot ← Approve / deny workflow
```

---

## Quick Start

### Step 1 — Edit config.yaml

Open `config.yaml` and change the `executable` path to match where Claims Desktop
is installed on your machine:

```yaml
application:
  executable: "C:\\Program Files\\ClaimsDesktop\\ClaimsDesktop.exe"
```

### Step 2 — Edit locators.yaml

Open Accessibility Insights for Windows (free Microsoft tool), hover over each
button and field in Claims Desktop, and copy the `AutomationId` values into
`locators.yaml`. The locators already provided are examples — your app may use
different IDs.

### Step 3 — Edit test credentials

In `tests/login_tests.robot` and `tests/claim_submission_tests.robot`, update:

```robotframework
${VALID_USERNAME}     your-test-username@company.com
${VALID_PASSWORD}     YourTestPassword
```

### Step 4 — Run the tests

```powershell
# Run all tests
.\run_tests.ps1

# Run only the smoke tests
.\run_tests.ps1 -Tags smoke

# Run only login tests
.\run_tests.ps1 -Suite login
```

The HTML report opens automatically when the run finishes.

---

## Finding AutomationIds

1. Download **Accessibility Insights for Windows**:
   https://accessibilityinsights.io/downloads/

2. Launch Claims Desktop.

3. In Accessibility Insights, click the crosshair icon, then hover over a
   button or field in the app.

4. The panel on the right shows `AutomationId`, `Name`, `ClassName`, and
   `ControlType` — copy whichever values are present into `locators.yaml`.

**Tip:** `AutomationId` is the most reliable. If it's empty, use `Name`.
If both are empty, use `ClassName` as a last resort.

---

## Test Organisation

| File | Tests | Tags |
|------|-------|------|
| `login_tests.robot` | Valid login, wrong password, empty fields | `smoke login regression negative` |
| `claim_submission_tests.robot` | Submit claim, cancel, search | `smoke claims regression negative search` |
| `supervisor_workflow_tests.robot` | Approve, deny, role check | `supervisor approval smoke` |

Run only smoke tests for a fast pre-deployment check:
```powershell
.\run_tests.ps1 -Tags smoke
```

---

## Reports

After each run, three files are created in `reports/<timestamp>/`:

| File | Contents |
|------|----------|
| `report.html` | Pass/fail summary with timing — share this with your team |
| `log.html` | Step-by-step execution details with screenshots |
| `output.xml` | Machine-readable results for CI/CD dashboards |
