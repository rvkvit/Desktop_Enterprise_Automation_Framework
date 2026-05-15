        *** Settings ***
        Resource    platform_settings.resource
        Resource    ../screens/login/keywords.resource
Resource    ../screens/claims_entry/keywords.resource
Resource    ../screens/dashboard/keywords.resource

        *** Keywords ***
        # ---------------------------------------------------------------------------
        # Add business-level keywords here.
        # Business keywords compose screen keywords into workflows.
        # They must NOT call platform keywords (Input Text, Click, etc.) directly.
        # ---------------------------------------------------------------------------

        # Example — replace with real workflows:
        #
        # Complete Login Workflow
        #     [Documentation]    Example business workflow — replace with real steps.
        #     [Arguments]    ${example_value}
        #     Launch Application
        #     Enter Example Text    ${example_value}
        #     Click Example Button
        #
        # Verify Result Is Shown
        #     [Documentation]    Asserts the result label contains the expected value.
        #     [Arguments]    ${expected}
        #     ${actual}=    Read Example Label
        #     Should Contain    ${actual}    ${expected}
