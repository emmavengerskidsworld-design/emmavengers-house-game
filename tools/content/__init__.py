"""Emmavengers World content library tools (Stage 1).

Modules:
  common   - canonical JSON, hashing, localized-text detection, voice-file hashing (FNV-1a, same as the app)
  source   - loads the authoring source (content/src) into records
  validate - JSON Schema + cross-record checks, produces issues
  compile  - builds content/library (catalog -> collection indexes -> packs), registry lock, report
  hydrate  - reads a compiled library back into records (what the app's library.js does)
  legacy   - rebuilds the pre-Stage-1 shapes (lands.json, country packs) from records, for the current screens
  migrate_v0 - one-time conversion of the pre-Stage-1 files into content/src (kept for the lossless test)
"""
