*** Settings ***
Resource    platform_settings.resource
Resource    ../screens/notepad/keywords.resource

*** Keywords ***
Open Notepad And Type
    [Documentation]    Launches Notepad and types the given text into the editor.
    [Arguments]    ${text}
    Launch Application
    Enter Text In Editor    ${text}

Verify Text Was Typed
    [Documentation]    Asserts that the editor contains the expected text.
    [Arguments]    ${expected_text}
    ${actual}=    Read Editor Content
    Should Contain    ${actual}    ${expected_text}
