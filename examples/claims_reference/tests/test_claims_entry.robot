*** Settings ***
Resource         ../resources/business_keywords.resource
Suite Teardown   Close Application

*** Test Cases ***
Claims Entry Smoke Test
    [Documentation]    Replace with a real test scenario for the Claims Entry screen.
    ...                Test files must contain ONLY business keyword calls.
    [Tags]    smoke    claims_entry
    Launch Application
    # Add your business keyword calls below — no platform keywords, no locator names:
    # Complete Claims Entry Workflow    example_value
    # Verify Result Is Shown       expected_result

Claims Entry Regression Test
    [Documentation]    Replace with a regression scenario.
    [Tags]    regression    claims_entry
    Launch Application
    # Add regression keyword calls here
