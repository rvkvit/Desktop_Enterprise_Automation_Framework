*** Settings ***
Resource         ../resources/business_keywords.resource
Suite Teardown   Close Application

*** Test Cases ***
Login Smoke Test
    [Documentation]    Replace with a real test scenario for the Login screen.
    ...                Test files must contain ONLY business keyword calls.
    [Tags]    smoke    login
    Launch Application
    # Add your business keyword calls below — no platform keywords, no locator names:
    # Complete Login Workflow    example_value
    # Verify Result Is Shown       expected_result

Login Regression Test
    [Documentation]    Replace with a regression scenario.
    [Tags]    regression    login
    Launch Application
    # Add regression keyword calls here
