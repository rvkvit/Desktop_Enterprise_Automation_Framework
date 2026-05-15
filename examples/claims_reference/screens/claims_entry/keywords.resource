*** Settings ***
Resource    ../../resources/platform_settings.resource

*** Keywords ***
Click Example Button
    [Documentation]    Clicks the example button on the Claims Entry screen.
    Click    CLAIMS_ENTRY.EXAMPLE_BUTTON

Enter Example Text
    [Documentation]    Types text into the example field on the Claims Entry screen.
    [Arguments]    ${text}
    Input Text    CLAIMS_ENTRY.EXAMPLE_FIELD    ${text}

Read Example Label
    [Documentation]    Returns the current text of the example label.
    ${value}=    Get Text    CLAIMS_ENTRY.EXAMPLE_LABEL
    RETURN    ${value}
