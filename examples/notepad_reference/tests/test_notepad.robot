*** Settings ***
Resource         ../resources/business_keywords.resource
Suite Teardown   Close Application

*** Test Cases ***
Type Text Into Notepad And Verify
    [Documentation]    Verifies Notepad can be launched and text typed end-to-end.
    ...                Demonstrates the 3-tier keyword architecture:
    ...                  Test file → business keyword → screen keyword → platform keyword.
    [Tags]    smoke    notepad
    Open Notepad And Type    Hello from Desktop Automation Platform!
    Verify Text Was Typed    Hello
