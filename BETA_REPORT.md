# Turbo Sort 3.0.0b1 beta report

## Local validation — 2026-09-20

Tested with Python **3.12.14 on Windows**, using disposable synthetic files.
No personal media library was used or modified.

### Regression iterations

1. Initial suite: 42 tests, one failure and one host-dependent skip. An
   underscore-separated episode name was rejected because regular-expression
   word boundaries treat underscores as word characters.
2. Corrected separators: 42 tests, 41 passed, one skipped.
3. Expanded failure coverage: **50 tests, 49 passed, one skipped**. Includes
   2,000 deterministic generated episode names, CLI preview/apply/repeat,
   collisions, language subtitles, dates, source changes, permission errors,
   simulated disk-full and corrupt-copy failures, and exclusive-publication races.

The skipped test requires creating a real symbolic link, which this local
Windows environment does not allow. Python compilation checks also passed.

### Two independent end-to-end batches

Each batch had 305 input files: 100 episodes, 200 language subtitles, one
12 MiB movie, and four deliberately ambiguous/conflicting inputs.

| Batch | Preview | Apply | Repeat apply | Hash preservation |
|---|---|---|---|---|
| 1 | 301 planned, 4 skipped; 1.965 s | 301 moved, 0 failed; 10.743 s | 0 moved; 0.268 s | All 305 contents preserved |
| 2 | 301 planned, 4 skipped; 1.832 s | 301 moved, 0 failed; 11.798 s | 0 moved; 0.225 s | All 305 contents preserved |

Both previews left the filesystem unchanged. Both repeats left the organized
files unchanged. All four skipped sources remained. Timings include Python
startup and local filesystem overhead; these are smoke-test timings, not a
benchmark of real multi-gigabyte media or network storage.

## Good

- The known cleanup/data-loss defects have regression coverage.
- Existing destination files are preserved even in a simulated publication race.
- Movie years, real dates, multi-episode numbers and subtitle languages survive.
- Processing no longer starts on import, and configuration errors are visible.
- Standard-library-only implementation; no obsolete notification dependency.

## Tradeoffs

- Copying and reading back every destination costs I/O and temporary disk space.
  A same-volume rename would be faster, but this beta prioritizes verification.
- Conservative parsing skips uncertain inputs rather than guessing. Numeric-only
  episode notation, quality-only movies and range syntax require manual renaming.
- Filename parsing cannot replace a metadata database; titles containing years
  or unusual release names can still need human review.

## Remaining limits

- This report establishes local Python 3.12/Windows results only. The GitHub
  workflow separately tests Python 3.11–3.14 on Windows and Linux; its results
  must be checked in Actions and are not implied by these local runs.
- No real second disk, network share, forced process kill or power failure was
  tested. Publication uses Windows no-replace rename or POSIX hard links.
- Failed source deletion can leave two complete copies. A process kill may
  leave a clearly named partial file. Recovery is manual, not transactional.
- Directory checks do not provide a security boundary against an adversary
  replacing paths during execution. Run one instance against trusted files
  that are no longer being written.
- File contents and modification time are preserved; filesystem-specific
  permissions, alternate streams and extended attributes are not promised.

This remains a beta with explicit limitations, not a claim of production
certification or guaranteed compatibility with future Python versions.
