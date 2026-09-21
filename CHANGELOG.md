# Changelog

## Unreleased

Reject ambiguous episode ranges with repeated season numbers, spaces, or
separated episode tokens instead of silently keeping only the first episode.
Preserve apostrophes, backslashes, and Unicode in generated TOML strings, and
validate generated TOML before replacing a configuration or its backup.
Add regression tests for both fixes and source-file retention.

## 3.0.0b1 — 2026-09-20

Modernize the supplied v2.3 script for Python 3.11+ with typed dataclasses,
pathlib, argparse, TOML configuration, validated templates, and import-safe entry
points. Keep the GPL-3.0-or-later license and original attribution.

Fix deletion after skipped moves, cleanup-setting shadowing, filename-prefix
deletion, subtitle language collisions and queue growth, year-at-end indexing,
numeric-month formatting, and overly broad hash detection. Add explicit
multi-episode parsing, modern video/sidecar extensions and 4K/8K quality fields.

Default to preview. Never overwrite destinations. Stage and verify file contents
before removing a source. Detect plan collisions, changing sources, symlinks and
overlapping directory trees. Cleanup removes only empty directories after
successful moves. Preserve ambiguous files and report errors visibly.

Breaking changes: replace source-code settings with CLI/TOML; remove destructive
cleanup, overwrite, obsolete desktop notifications and guessed compact episode
numbers. See README.txt for migration and operational limitations.

Add regression, generated-filename, failure-injection and repeated CLI beta tests.
Add `turbo_setup.py`, a guided configuration wizard that previews choices,
validates templates and paths, backs up existing TOML, and never edits code.
Earlier release notes remain in changelog.txt.
