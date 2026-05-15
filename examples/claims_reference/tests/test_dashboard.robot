*** Settings ***
Resource         ../resources/business_keywords.resource
Suite Teardown   Close Application

*** Test Cases ***
Dashboard Smoke Test
    [Documentation]    Replace with a real test scenario for the Dashboard screen.
    ...                Test files must contain ONLY business keyword calls.
    [Tags]    smoke    dashboard
    Launch Application
    # Add your business keyword calls below — no platform keywords, no locator names:
    # Complete Dashboard Workflow    example_value
    # Verify Result Is Shown       expected_result

Dashboard Regression Test
    [Documentation]    Replace with a regression scenario.
    [Tags]    regression    dashboard
    Launch Application
    # Add regression keyword calls here
