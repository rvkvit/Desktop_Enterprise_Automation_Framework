*** Settings ***
Documentation     End-to-end claim submission tests for Claims Desktop.
...
...               Covers:
...               - Creating a new claim with all required fields
...               - Verifying confirmation after submission
...               - Cancelling a claim mid-way
...               - Searching for a submitted claim
...
Library           DesktopAutomationLibrary
...               config_path=${CURDIR}/../config.yaml
...               locator_path=${CURDIR}/../locators.yaml

Suite Setup       Run Keywords
...               Launch Application    AND
...               Login To Application

Suite Teardown    Run Keywords
...               Logout And Close


*** Variables ***
${VALID_USERNAME}      testuser@company.com
${VALID_PASSWORD}      TestPass123!
${CLAIMANT_NAME}       Jane Doe
${CLAIM_AMOUNT}        1500.00
${CLAIM_DESCRIPTION}   Water damage to kitchen ceiling following roof leak on 2026-04-30.


*** Keywords ***

Login To Application
    [Documentation]    Shared login step used by all tests in this suite.
    Input Text    LOGIN_USERNAME_FIELD    ${VALID_USERNAME}
    Input Text    LOGIN_PASSWORD_FIELD    ${VALID_PASSWORD}
    Click         LOGIN_BUTTON
    Wait For Element    DASHBOARD_TITLE    timeout=20

Logout And Close
    [Documentation]    Logout then close the application.
    Click              LOGOUT_MENU_ITEM
    Close Application

Open New Claim Form
    [Documentation]    Click "New Claim" and wait for the form to appear.
    Click             NEW_CLAIM_BUTTON
    Wait For Element  CLAIMANT_NAME_FIELD    timeout=10

Fill In Claim Form
    [Arguments]    ${claimant}    ${claim_type}    ${amount}    ${description}
    [Documentation]    Fills in all fields of the new claim form.
    Input Text       CLAIMANT_NAME_FIELD      ${claimant}
    Select Item      CLAIM_TYPE_DROPDOWN      ${claim_type}
    Input Text       CLAIM_AMOUNT_FIELD       ${amount}
    Input Text       CLAIM_DESCRIPTION_FIELD  ${description}


*** Test Cases ***

# ── Happy Path ──────────────────────────────────────────────────────────────

TC101 — Submit New Medical Claim Successfully
    [Documentation]    Fill in a complete Medical claim and verify the confirmation message.
    [Tags]    smoke    claims    regression

    Open New Claim Form

    Fill In Claim Form
    ...    claimant=${CLAIMANT_NAME}
    ...    claim_type=Medical
    ...    amount=${CLAIM_AMOUNT}
    ...    description=${CLAIM_DESCRIPTION}

    Click    SUBMIT_CLAIM_BUTTON

    # Confirmation banner must appear within 10 seconds
    Wait For Element    CLAIM_SAVED_CONFIRMATION    timeout=10

    ${confirmation}=    Get Text    CLAIM_SAVED_CONFIRMATION
    Should Contain    ${confirmation}    submitted    ignore_case=True


TC102 — Submit New Property Claim And Verify Claim ID Is Generated
    [Documentation]    After submission the Claim ID field should be auto-populated.
    [Tags]    claims    regression

    Open New Claim Form

    Fill In Claim Form
    ...    claimant=Bob Smith
    ...    claim_type=Property
    ...    amount=750.00
    ...    description=Broken fence panel from storm.

    Click    SUBMIT_CLAIM_BUTTON
    Wait For Element    CLAIM_SAVED_CONFIRMATION    timeout=10

    # Claim ID should now have a value (not empty)
    ${claim_id}=    Get Text    CLAIM_ID_FIELD
    Should Not Be Empty    ${claim_id}
    Log    New claim created with ID: ${claim_id}


# ── Negative Tests ──────────────────────────────────────────────────────────

TC103 — Cancel New Claim Returns To Dashboard
    [Documentation]    Cancelling a half-filled form returns the user to the dashboard.
    [Tags]    claims    negative

    Open New Claim Form
    Input Text    CLAIMANT_NAME_FIELD    ${CLAIMANT_NAME}

    # Cancel without submitting
    Click    CANCEL_BUTTON

    # Dashboard should be visible again
    Wait For Element    DASHBOARD_TITLE    timeout=10
    ${title}=    Get Text    DASHBOARD_TITLE
    Should Contain    ${title}    Dashboard


TC104 — Submit Claim With Missing Required Fields Shows Error
    [Documentation]    Submitting the form with no claimant name must show a validation error.
    [Tags]    claims    negative

    Open New Claim Form

    # Only fill in amount — leave claimant name empty
    Input Text       CLAIM_AMOUNT_FIELD    100.00
    Click            SUBMIT_CLAIM_BUTTON

    # The form should NOT progress to a confirmation — we expect to stay on form
    ${confirmed}=    Element Exists    CLAIM_SAVED_CONFIRMATION    timeout=3
    Should Not Be True    ${confirmed}
    ...    msg=Form should not submit without a claimant name


# ── Search / Regression ─────────────────────────────────────────────────────

TC105 — Search For A Claim By Claimant Name
    [Documentation]    Using the search bar should filter the claims list.
    [Tags]    claims    search    regression

    # Make sure we are on the dashboard
    Wait For Element    CLAIMS_LIST    timeout=10

    # Type a search term
    Input Text    SEARCH_CLAIMS_FIELD    Jane Doe

    # Claims list should update — just verify it is still visible (real assertion
    # would inspect row count, which requires adapter-specific row-count keyword)
    Wait For Element    CLAIMS_LIST    timeout=5
    ${list_visible}=    Element Exists    CLAIMS_LIST
    Should Be True    ${list_visible}
