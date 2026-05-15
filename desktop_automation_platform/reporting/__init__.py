"""
Reporting package — Phase 3/4 deliverable.

Planned modules:
  execution_tracker.py   — aggregates ActionResult events per test
  report_generator.py    — produces JSON / HTML execution reports
  robot_listener.py      — Robot Framework listener that hooks into output.xml

Reports include:
  - per-keyword execution time
  - adapter used per session
  - locator resolution path (which strategy succeeded)
  - screenshots on failure
  - recovery attempts
  - adapter diagnostics
"""
