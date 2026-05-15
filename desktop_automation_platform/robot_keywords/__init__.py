"""
Robot Framework keyword layer — Phase 3 deliverable.

Planned modules:
  desktop_keywords.py   — all 20 adapter-agnostic RF keywords
  keyword_registry.py   — keyword metadata and alias mapping

All keywords delegate to AdapterManager.get_adapter_for_session() and
accept locator names (strings) resolved via the LocatorRepository.
"""
