*** Settings ***
Documentation     Login and authentication test suite for Claims Desktop.
...
...               These tests verify that:
...               - Valid credentials grant access to the Dashboard
...               - Invalid credentials show an error message
...               - The app can be launched and closed cleanly
...
Library           DesktopAutomationLibrary
...               config_path=${CURDIR}/../config.yaml
...               locator_path=${CURDIR}/../locators.yaml

Suite Setup       Launch Application
Suite Teardown    Close Application

*** Variables ***
# Test data — change these to match your environment
${VALID_USERNAME}     testuser@company.com
${VALID_PASSWORD}     TestPass123!
${INVALID_PASSWORD}   WrongPassword999


*** Test Cases ***

# ── Happy Path ──────────────────────────────────────────────────────────────

TC001 — Successful Login With Valid Credentials
    [Documentation]    Log in with correct credentials and verify the dashboard loads.
    [Tags]    smoke    login    regression

    # Type username and password
    Input Text    LOGIN_USERNAME_FIELD    ${VALID_USERNAME}
    Input Text    LOGIN_PASSWORD_FIELD    ${VALID_PASSWORD}

    # Click the login button
    Click    LOGIN_BUTTON

    # Verify we reached the dashboard (wait up to 20 seconds)
    Wait For Element    DASHBOARD_TITLE    timeout=20

    # Confirm the page heading is correct
    ${title}=    Get Text    DASHBOARD_TITLE
    Should Contain    ${title}    Dashboard


# ── Negative Tests ──────────────────────────────────────────────────────────

TC002 — Login Fails With Wrong Password
    [Documentation]    Wrong password shows an error message without crashing.
    [Tags]    login    negative

    Input Text    LOGIN_USERNAME_FIELD    ${VALID_USERNAME}
    Input Text    LOGIN_PASSWORD_FIELD    ${INVALID_PASSWORD}
    Click         LOGIN_BUTTON

    # Error banner should appear within 5 seconds
    Wait For Element    LOGIN_ERROR_MESSAGE    timeout=5

    # Check the error text
    ${err}=    Get Text    LOGIN_ERROR_MESSAGE
    Should Not Be Empty    ${err}

TC003 — Login Fails With Empty Fields
    [Documentation]    Submitting empty credentials should show a validation error.
    [Tags]    login    negative

    # Leave fields blank and hit login
    Click    LOGIN_BUTTON

    # An error (or at least the error element) must appear
    ${error_visible}=    Element Exists    LOGIN_ERROR_MESSAGE    timeout=3
    Should Be True    ${error_visible}    msg=Expected an error message for empty credentials
