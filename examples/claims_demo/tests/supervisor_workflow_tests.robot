*** Settings ***
Documentation     Supervisor claim approval / denial workflow tests.
...
...               These tests simulate a supervisor reviewing submitted claims.
...               They depend on TC101/TC102 having created claims first —
...               run the full suite together to get realistic data.
...
Library           DesktopAutomationLibrary
...               config_path=${CURDIR}/../config.yaml
...               locator_path=${CURDIR}/../locators.yaml

Suite Setup       Run Keywords
...               Launch Application    AND
...               Login As Supervisor

Suite Teardown    Run Keywords
...               Logout And Close


*** Variables ***
${SUPERVISOR_USERNAME}    supervisor@company.com
${SUPERVISOR_PASSWORD}    SuperPass456!
# Replace with a real claim ID from your test environment
${KNOWN_CLAIM_ID}         CLM-2026-001


*** Keywords ***

Login As Supervisor
    Input Text    LOGIN_USERNAME_FIELD    ${SUPERVISOR_USERNAME}
    Input Text    LOGIN_PASSWORD_FIELD    ${SUPERVISOR_PASSWORD}
    Click         LOGIN_BUTTON
    Wait For Element    DASHBOARD_TITLE    timeout=20

Logout And Close
    Click              LOGOUT_MENU_ITEM
    Close Application

Open Claim By Search
    [Arguments]    ${claim_id}
    [Documentation]    Search for a claim by ID and open the detail view.
    Input Text      SEARCH_CLAIMS_FIELD    ${claim_id}
    Wait For Element    CLAIMS_LIST    timeout=5
    # Double-click the first search result to open the claim detail
    Double Click    CLAIMS_LIST


*** Test Cases ***

TC201 — Supervisor Can Approve A Claim
    [Documentation]    Opens an Open claim and approves it.
    [Tags]    supervisor    approval    regression

    Open Claim By Search    ${KNOWN_CLAIM_ID}

    # Check initial status
    Wait For Element    CLAIM_STATUS_LABEL    timeout=10
    ${initial_status}=    Get Text    CLAIM_STATUS_LABEL
    Log    Initial status: ${initial_status}

    # Click Approve
    Click    APPROVE_CLAIM_BUTTON

    # Status should change to Approved
    Wait For Element    CLAIM_STATUS_LABEL    timeout=10
    ${new_status}=    Get Text    CLAIM_STATUS_LABEL
    Should Contain    ${new_status}    Approved    ignore_case=True


TC202 — Supervisor Can Deny A Claim
    [Documentation]    Opens a different Open claim and denies it.
    [Tags]    supervisor    approval    regression

    # Use a second known claim ID or rely on a fixture that creates one
    Open Claim By Search    ${KNOWN_CLAIM_ID}

    Click    DENY_CLAIM_BUTTON

    Wait For Element    CLAIM_STATUS_LABEL    timeout=10
    ${new_status}=    Get Text    CLAIM_STATUS_LABEL
    Should Contain    ${new_status}    Denied    ignore_case=True


TC203 — Approve Button Is Visible For Supervisor
    [Documentation]    The Approve button must be present when a supervisor is logged in.
    [Tags]    supervisor    smoke

    Open Claim By Search    ${KNOWN_CLAIM_ID}

    ${approve_visible}=    Element Exists    APPROVE_CLAIM_BUTTON    timeout=5
    Should Be True    ${approve_visible}
    ...    msg=Approve button should be visible for supervisor role
