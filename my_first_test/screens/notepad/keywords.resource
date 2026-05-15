*** Settings ***
Resource    ../../resources/platform_settings.resource

*** Keywords ***
Enter Text In Editor
    [Documentation]    Types the given text into the Notepad text area.
    [Arguments]    ${text}
    Input Text    NOTEPAD.TEXT_AREA    ${text}

Read Editor Content
    [Documentation]    Returns the full text currently in the Notepad text area.
    ${content}=    Get Text    NOTEPAD.TEXT_AREA
    RETURN    ${content}

Clear Editor
    [Documentation]    Clears all text from the Notepad text area.
    Clear Text    NOTEPAD.TEXT_AREA
