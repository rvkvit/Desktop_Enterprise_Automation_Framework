*** Settings ***
Resource    ../../resources/platform_settings.resource

*** Keywords ***
Click Example Button
    [Documentation]    Clicks the example button on the Dashboard screen.
    Click    DASHBOARD.EXAMPLE_BUTTON

Enter Example Text
    [Documentation]    Types text into the example field on the Dashboard screen.
    [Arguments]    ${text}
    Input Text    DASHBOARD.EXAMPLE_FIELD    ${text}

Read Example Label
    [Documentation]    Returns the current text of the example label.
    ${value}=    Get Text    DASHBOARD.EXAMPLE_LABEL
    RETURN    ${value}
