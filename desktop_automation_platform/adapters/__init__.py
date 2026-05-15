"""
Adapter package — pluggable desktop automation engine implementations.

Each adapter sub-package (flaui/, winappdriver/, etc.) contains:
  adapter.py      — IApplicationAdapter implementation
  translator.py   — ILocatorTranslator implementation
  scanner.py      — ILocatorScanner implementation (optional per adapter)

The AdapterManager is the entry point for all adapter lifecycle operations.
"""
