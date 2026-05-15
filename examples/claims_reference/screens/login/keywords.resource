*** Settings ***
Resource    ../../resources/platform_settings.resource

*** Keywords ***
Click Example Button
    [Documentation]    Clicks the example button on the Login screen.
    Click    LOGIN.EXAMPLE_BUTTON

Enter Example Text
    [Documentation]    Types text into the example field on the Login screen.
    [Arguments]    ${text}
    Input Text    LOGIN.EXAMPLE_FIELD    ${text}

Read Example Label
    [Documentation]    Returns the current text of the example label.
    ${value}=    Get Text    LOGIN.EXAMPLE_LABEL
    RETURN    ${value}
