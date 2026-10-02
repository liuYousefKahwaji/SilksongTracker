# Retired in-game map overlay

This is a recovery archive of the v0.3.5-beta experiment that drew the tracker map over Silksong's full in-game menu map. It is intentionally excluded from the active plugin and tracker. The browser-based tracker map and its live Hornet marker remain active.

The archive contains the overlay source and its v0.3.5 bridge host/project, the matching previously built DLL, documentation, and the tracker-side image/API adapter plus its tests and launcher/dependency snapshots. `tracker-adapter/README.md` is the repository README as it was when archived. The binary was hash-verified against the existing release build before it was copied.

Do not copy the archived DLL over the active plugin unless intentionally restoring the old overlay. Its controller/input suppression and tile-decoding path were not validated in-game and were removed at the user's request.
