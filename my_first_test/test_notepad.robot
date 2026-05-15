*** Settings ***
Resource         resources/business_keywords.resource
Suite Teardown   Close Application

*** Test Cases ***
Type Text Into Notepad And Verify
    [Documentation]    Verifies Notepad can be launched and text typed, using business-level keywords only.
    [Tags]    smoke
    Open Notepad And Type    Hello from Desktop Automation Platform!
    Verify Text Was Typed    Hello
