Turbo Sort 3.0 beta
===================

Preview-first movie and TV file organization for Python 3.11 and newer.
No third-party packages are required. Derived from Michael Riha's turbo_sort
v2.3; GPL-3.0-or-later (see LICENSE.txt). This beta changes the configuration
interface and intentionally removes destructive legacy behavior.

Quick start
-----------
Install a supported Python 3.11+ interpreter. Open a terminal in this folder.
Preview (no files or directories are changed):

  python turbo_sort.py --source "C:\Downloads\Completed" --tv "C:\Media\TV" --movies "C:\Media\Movies"

After reviewing the output, repeat the command with --apply to perform moves.
The default minimum video size is 100 MiB. Use --min-size-mb 0 for small samples.
Only process completed downloads; stop downloaders or other writers first.
Source and destination directories must be separate, non-overlapping trees.

Alternatively edit a copy of config.example.toml and run:

  python turbo_sort.py --config config.toml
  python turbo_sort.py --config config.toml --apply

CLI settings override configuration entries. Relative paths are relative to
the current working directory. Neither a TOML file nor an import can turn on
--apply: it must be explicitly supplied on the command line.

Behavior and safety
-------------------
* A complete plan is built before file moves start.
* Existing destinations are never overwritten, even when they appear after
  planning. Multiple inputs targeting one name are all skipped.
* Each move copies into a temporary file in the destination directory,
  flushes it, checks its size and SHA-256 hash, publishes it without replacing
  another file, and only then removes the unchanged source.
* Subtitle languages and qualifiers survive: .en.srt and .fr.forced.srt stay
  separate. Subtitles only move after their video successfully moves.
* --cleanup-empty removes only empty source subdirectories touched by successful
  moves. It never removes the source root or deletes leftover files.
* Symlinks, Windows junctions and other reparse points are rejected.
* Re-running on the same completed input performs no additional moves.
* Messages report skips and failures, followed by a JSON count summary.
  Exit codes: 0 = completed (possibly with skips), 1 = operation/scan failure,
  2 = invalid arguments or configuration. A zero exit code does not imply that
  every input was recognized; review SKIP messages.

File recognition
----------------
Supported video extensions: mkv, avi, mp4, ts, m4v, mov, webm.
Supported sidecars: srt, ass, ssa, vtt, sub, idx, srr (case-insensitive).
Examples:

  The.Office.S06E03.mkv       -> TV/The Office/Season 6/The Office S06 E03.mkv
  Show.S01E01E02.mkv          -> TV/Show/Season 1/Show S01 E01E02.mkv
  Show.10x101.mkv             -> TV/Show/Season 10/Show S10 E101.mkv
  News.2024.03.05.mkv         -> TV/News/News Mar 05 2024.mkv
  Movie.2020.2160p.mkv        -> Movies/Movie (2020).mkv

Spaces, dots and underscores are accepted as separators. Spelling, hyphenated
titles, Unicode, acronyms and country identifiers are preserved. Dates must
be real calendar dates. Entire 32/40/64-character hexadecimal basenames use
their parent folder name for recognition. A mere hexadecimal prefix does not.

Ambiguous plain titles, quality-only movie names, compact episode numbers
(Show.101), and episode ranges (S01E01-E03) are skipped. Use explicit
S01E01E02 notation for multiple episodes. No online metadata lookup is made;
the parser cannot guarantee that a year is a release year rather than part of
a title. Release-group prefixes are not automatically removed.

Naming templates
----------------
Both / and backslash separators are accepted. Templates must be relative,
with no empty components, . or ... Invalid characters in generated filename
components are replaced with underscores; Windows reserved names are prefixed
with an underscore. Missing fields or unknown tokens cause a skip/error rather
than silently producing a fallback name. Templates do not include extensions.

All: %t title, %T uppercase title, %o original basename, %% literal percent.
Episodes: %s season, %0s padded season, %e episodes, %0e padded episodes.
Dated shows: %y year, %m month, %0m padded month, %d day, %0d padded day,
             %fm month name, %FM uppercase month, %sm abbreviation,
             %SM uppercase abbreviation.
Movies: %y year, %q quality (2160p/4k/8k etc., only if recognized).

Migration from 2.3
------------------
Old editable globals are replaced by CLI arguments / TOML:
  sourcedir -> source; tvdest -> tv; moviedest -> movies;
  min_size -> min_size_mb; undated_fs/dated_fs/movie_fs keep their names;
  satellites -> satellites or --no-satellites;
  no_rename -> preview is now the default; use --apply to move files.

Removed: overwrite, remove_CC, clean_mode, remove_src, notify/pynotify,
stay_open/raw_input, truncate, and silent exception handling. Old cleanup=True
does not carry over; the replacement cleanup_empty defaults to false.
Legacy globals or unknown config keys are rejected, not silently accepted.

Limitations
-----------
Verified copying is slower than renaming on one disk and requires free space
for another full copy of the file. File contents and modification time are
preserved; ownership, ACLs, alternate streams, and extended attributes are not
promised. POSIX publication requires hard-link support on the destination
filesystem. Unsupported filesystems fail with the source retained.

This is not a transaction across an entire video/subtitle group. A subtitle
failure can leave that subtitle in the source after its video moved. If source
removal fails, two complete copies may remain; the next run skips the existing
destination. A killed process can leave a .turbo-sort-*.partial temporary file;
inspect it manually. There is no automatic recovery or undo journal.

Source stat checks detect ordinary changes during processing, but do not lock
out writers. Filesystem races, hostile directory replacement, arbitrary
concurrent edits, and power-loss durability are not guaranteed. Run against
trusted, completed files with one organizer instance at a time.

Tests
-----
  python -m unittest -v test_turbo_sort
  python beta_scenarios.py

All tests create disposable temporary directories and never use your media
library. See BETA_REPORT.md for tested versions, results and remaining limits.
