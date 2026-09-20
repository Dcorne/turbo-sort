#!/usr/bin/env python3
"""Turbo Sort 3.0 beta: preview-first media organization for Python 3.11+.

Derived from turbo_sort v2.3, Copyright (C) 2012-2013 Michael Riha.
Licensed under GPL-3.0-or-later; distributed WITHOUT ANY WARRANTY.
"""

# Copyright (C) 2012-2013 Michael Riha
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Modified 2026-09-20: Python 3.11+ preview-first beta.

from __future__ import annotations

import argparse
import calendar
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import sys
import tempfile
import tomllib
from typing import Callable

VERSION = "3.0.0b1"
VIDEO_EXTENSIONS = frozenset({".mkv", ".avi", ".mp4", ".ts", ".m4v", ".mov", ".webm"})
SUBTITLE_EXTENSIONS = frozenset({".srt", ".ass", ".ssa", ".vtt", ".sub", ".idx", ".srr"})
HASH = re.compile(r"(?:[a-f0-9]{32}|[a-f0-9]{40}|[a-f0-9]{64})", re.I)
EPISODE = re.compile(r"(?<![^\W_])s(?P<season>\d{1,2})(?P<episodes>(?:e\d{1,3})+)(?![^\W_])", re.I)
X_EPISODE = re.compile(r"(?<![^\W_])(?P<season>\d{1,2})x(?P<episode>\d{1,3})(?![^\W_])", re.I)
DATE = re.compile(r"(?<!\d)((?:19|20)\d{2})[ ._-](\d{2})[ ._-](\d{2})(?!\d)")
YEAR = re.compile(r"(?<![^\W_])((?:19|20)\d{2})(?![^\W_])")
QUALITY = re.compile(r"(?<![^\W_])(2160p|1080p|1080i|720p|576p|480p|4320p|4k|8k|xvid)(?![^\W_])", re.I)
TOKEN = re.compile(r"%(0[esmd]|fm|FM|sm|SM|[tToesmdyq%])")
RESERVED = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.I)


@dataclass(frozen=True)
class Config:
    source: Path
    tv: Path
    movies: Path
    min_size_mb: float = 100
    undated_fs: str = "%t/Season %s/%t S%0s E%0e"
    dated_fs: str = "%t/%t %sm %0d %y"
    movie_fs: str = "%t (%y)"
    satellites: bool = True
    cleanup_empty: bool = False


@dataclass(frozen=True)
class Media:
    title: str
    kind: str
    original: str
    year: int | None = None
    season: int | None = None
    episodes: tuple[int, ...] = ()
    aired: date | None = None
    quality: str | None = None


@dataclass(frozen=True)
class Stamp:
    device: int
    inode: int
    size: int
    modified_ns: int


@dataclass(frozen=True)
class Move:
    source: Path
    destination: Path
    stamp: Stamp
    parent: Path | None = None


@dataclass
class Plan:
    moves: list[Move] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)
    errors: list[tuple[Path, str]] = field(default_factory=list)


def is_link(path: Path) -> bool:
    """Also reject Windows junctions and other reparse points."""
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def guard_path(path: Path) -> None:
    for item in (path, *path.parents):
        if os.path.lexists(item) and is_link(item):
            raise ValueError(f"Symbolic links / reparse points are not supported: {item}")


def stamp(path: Path) -> Stamp:
    guard_path(path)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"Not a regular file: {path}")
    return Stamp(info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def validate(config: Config) -> None:
    if not math.isfinite(config.min_size_mb) or config.min_size_mb < 0:
        raise ValueError("min_size_mb must be a finite nonnegative number")
    for path in (config.source, config.tv, config.movies):
        guard_path(path)
        if path.exists() and not path.is_dir():
            raise ValueError(f"Expected a directory: {path}")
    if not config.source.is_dir():
        raise ValueError(f"Source directory does not exist: {config.source}")
    source = config.source.resolve()
    for destination in (config.tv.resolve(), config.movies.resolve()):
        if source.is_relative_to(destination) or destination.is_relative_to(source):
            raise ValueError("Source and destination directories must not overlap")
    for template in (config.undated_fs, config.dated_fs, config.movie_fs):
        validate_template(template)


def validate_template(template: str) -> None:
    if not isinstance(template, str) or not template:
        raise ValueError("Naming templates must be nonempty strings")
    normalized = template.replace("\\", "/")
    if PureWindowsPath(template).drive or normalized.startswith("/"):
        raise ValueError("Naming templates must be relative paths")
    if any(part in {"", ".", ".."} for part in normalized.split("/")):
        raise ValueError("Empty, dot, and parent components are forbidden in templates")
    if "%" in TOKEN.sub("", template):
        raise ValueError(f"Unknown or incomplete template token: {template}")


def clean_component(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip().rstrip(". ")
    if not value or value in {".", ".."}:
        raise ValueError("Empty filename component")
    return "_" + value if RESERVED.match(value) else value


def title_text(value: str) -> str:
    # Preserve spelling, apostrophes, hyphens, acronyms and country identifiers.
    value = re.sub(r"[._]+", " ", value)
    return clean_component(re.sub(r"\s+", " ", value).strip(" []()-"))


def parse_media(path: Path) -> Media:
    name = path.parent.name if HASH.fullmatch(path.stem) else path.stem
    quality_match = QUALITY.search(name)
    quality = quality_match[1].lower() if quality_match else None
    episode_match = EPISODE.search(name) or X_EPISODE.search(name)
    if episode_match:
        if re.match(r"-e?\d", name[episode_match.end():], re.I):
            raise ValueError("Episode ranges are ambiguous; use explicit S01E01E02 notation")
        if episode_match.re is EPISODE:
            episodes = tuple(int(n) for n in re.findall(r"e(\d+)", episode_match["episodes"], re.I))
        else:
            episodes = (int(episode_match["episode"]),)
        return Media(title_text(name[:episode_match.start()]), "tv", path.stem,
                     season=int(episode_match["season"]), episodes=episodes, quality=quality)
    dated = DATE.search(name)
    if dated:
        aired = date(*(int(n) for n in dated.groups()))
        return Media(title_text(name[:dated.start()]), "dated", path.stem,
                     year=aired.year, aired=aired, quality=quality)
    # A year at the start may be part of the title (e.g. 2001 A Space Odyssey).
    years = [m for m in YEAR.finditer(name) if name[:m.start()].strip(" ._-([")]
    if years:
        year = years[-1]
        return Media(title_text(name[:year.start()]), "movie", path.stem,
                     year=int(year[1]), quality=quality)
    # Plain titles, compact episode numbers and quality-only names are ambiguous.
    raise ValueError("Unrecognized or ambiguous name; needs S01E01, 1x01, a date, or a movie year")


def format_media(media: Media, template: str) -> Path:
    validate_template(template)
    values = {"t": media.title, "T": media.title.upper(), "o": media.original, "%": "%"}
    if media.year is not None:
        values["y"] = str(media.year)
    if media.quality:
        values["q"] = media.quality
    if media.season is not None:
        values.update(s=str(media.season), **{"0s": f"{media.season:02}"})
        values["e"] = "E".join(str(n) for n in media.episodes)
        values["0e"] = "E".join(f"{n:02}" for n in media.episodes)
    if media.aired:
        day, month = media.aired.day, media.aired.month
        values.update(m=str(month), d=str(day), fm=calendar.month_name[month],
                      FM=calendar.month_name[month].upper(), sm=calendar.month_abbr[month],
                      SM=calendar.month_abbr[month].upper(), **{"0m": f"{month:02}", "0d": f"{day:02}"})

    def substitute(match: re.Match[str]) -> str:
        key = match[1]
        if key not in values:
            raise ValueError(f"Template needs missing field %{key}")
        # Values can never introduce additional folders into a template.
        return clean_component(values[key])

    return Path(*(clean_component(TOKEN.sub(substitute, part))
                  for part in template.replace("\\", "/").split("/")))


def path_key(path: Path) -> str:
    # Also catch collisions that would occur if a library is moved to Windows.
    return str(path.absolute()).casefold()


def collision(path: Path) -> bool:
    if os.path.lexists(path):
        return True
    if path.parent.is_dir():
        return any(p.name.casefold() == path.name.casefold() for p in path.parent.iterdir())
    return False


def build_plan(config: Config) -> Plan:
    validate(config)
    plan = Plan()
    candidates: list[Move] = []

    def walk_error(error: OSError) -> None:
        plan.errors.append((Path(error.filename or config.source), str(error)))

    for root, dirs, filenames in os.walk(config.source, followlinks=False, onerror=walk_error):
        directory = Path(root)
        kept = []
        for name in sorted(dirs):
            child = directory / name
            try:
                if is_link(child):
                    plan.skipped.append((child, "Linked directory skipped"))
                else:
                    kept.append(name)
            except OSError as exc:
                plan.errors.append((child, str(exc)))
        dirs[:] = kept
        files = [directory / name for name in sorted(filenames)]
        for path in files:
            if path.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            try:
                info = stamp(path)
                if info.size < config.min_size_mb * 1024 * 1024:
                    plan.skipped.append((path, "Below minimum size"))
                    continue
                media = parse_media(path)
                template = {"movie": config.movie_fs, "tv": config.undated_fs, "dated": config.dated_fs}[media.kind]
                target_root = config.movies if media.kind == "movie" else config.tv
                relative = format_media(media, template)
                destination = target_root / relative.parent / (relative.name + path.suffix.lower())
                guard_path(destination)
                if not destination.resolve().is_relative_to(target_root.resolve()):
                    raise ValueError("Destination escapes its configured directory")
                candidates.append(Move(path, destination, info))
                if config.satellites:
                    for sidecar in files:
                        if sidecar.suffix.lower() not in SUBTITLE_EXTENSIONS:
                            continue
                        stem, base = sidecar.stem, path.stem
                        if stem.casefold() != base.casefold() and not stem.casefold().startswith(base.casefold() + "."):
                            continue
                        suffix = stem[len(base):]  # .en, .fr.forced, etc.
                        # Do not claim a sidecar whose stem names another video.
                        if any(other != path and other.suffix.lower() in VIDEO_EXTENSIONS
                               and stem.casefold().startswith(other.stem.casefold())
                               and len(other.stem) > len(base) for other in files):
                            continue
                        try:
                            target = destination.with_name(clean_component(destination.stem + suffix) + sidecar.suffix.lower())
                            candidates.append(Move(sidecar, target, stamp(sidecar), path))
                        except (OSError, ValueError) as exc:
                            plan.skipped.append((sidecar, str(exc)))
            except OSError as exc:
                plan.errors.append((path, str(exc)))
            except ValueError as exc:
                plan.skipped.append((path, str(exc)))
    counts = Counter(path_key(item.destination) for item in candidates)
    blocked: set[Path] = set()
    for item in candidates:
        reason = None
        if item.parent in blocked:
            reason = "Parent video was skipped"
        elif counts[path_key(item.destination)] > 1:
            reason = "Multiple source files target this destination"
        elif collision(item.destination):
            reason = "Destination already exists; source retained"
        if reason:
            plan.skipped.append((item.source, reason))
            if item.parent is None:
                blocked.add(item.source)
        else:
            plan.moves.append(item)
    return plan


def digest(path: Path) -> bytes:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").digest()


def publish(staged: Path, destination: Path) -> None:
    """Install without replacement; fail closed on filesystems lacking support."""
    if os.name == "nt":
        # Windows rename refuses to replace an existing destination.
        os.rename(staged, destination)
    else:
        # POSIX rename can overwrite: use exclusive hard-link publication instead.
        os.link(staged, destination)
        staged.unlink()


def move_verified(item: Move) -> None:
    """Copy, verify, publish exclusively, then remove the unchanged source.

    A crash after publication can leave two complete copies, never deliberately
    destroys an existing destination, and never removes source before verification.
    """
    if stamp(item.source) != item.stamp:
        raise ValueError("Source changed since planning; source retained")
    guard_path(item.destination)
    if collision(item.destination):
        raise FileExistsError(f"Destination appeared after planning: {item.destination}")
    item.destination.parent.mkdir(parents=True, exist_ok=True)
    staged: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".turbo-sort-", suffix=".partial",
                                         dir=item.destination.parent, delete=False) as target:
            staged = Path(target.name)
            checksum = hashlib.sha256()
            with item.source.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    target.write(chunk)
                    checksum.update(chunk)
            target.flush()
            os.fsync(target.fileno())
        if stamp(item.source) != item.stamp:
            raise ValueError("Source changed while copying; source retained")
        if staged.stat().st_size != item.stamp.size or digest(staged) != checksum.digest():
            raise OSError("Copy verification failed; source retained")
        os.utime(staged, ns=(item.source.stat().st_atime_ns, item.stamp.modified_ns))
        guard_path(item.destination)
        if collision(item.destination):
            raise FileExistsError(f"Destination appeared while copying: {item.destination}")
        publish(staged, item.destination)
        if stamp(item.source) != item.stamp:
            raise ValueError("Source changed before removal; both copies retained")
        item.source.unlink()
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


def execute(plan: Plan, config: Config, *, apply: bool = False,
            emit: Callable[[str], None] = print) -> dict[str, int]:
    validate(config)
    result = {"planned": len(plan.moves), "moved": 0, "skipped": len(plan.skipped), "failed": len(plan.errors)}
    for path, reason in plan.skipped:
        emit(f"SKIP {path}: {reason}")
    for path, reason in plan.errors:
        emit(f"ERROR {path}: {reason}")
    succeeded: set[Path] = set()
    touched: set[Path] = set()
    for item in plan.moves:
        if item.parent and apply and item.parent not in succeeded:
            result["skipped"] += 1
            emit(f"SKIP {item.source}: parent video did not move")
            continue
        if not apply:
            emit(f"PREVIEW {item.source} -> {item.destination}")
            continue
        try:
            move_verified(item)
            succeeded.add(item.source)
            touched.add(item.source.parent)
            result["moved"] += 1
            emit(f"MOVED {item.source} -> {item.destination}")
        except (OSError, ValueError) as exc:
            result["failed"] += 1
            emit(f"ERROR {item.source}: {exc}")
    if apply and config.cleanup_empty:
        source_root = config.source.resolve()
        for directory in sorted(touched, key=lambda p: len(p.parts), reverse=True):
            while directory.resolve() != source_root and directory.resolve().is_relative_to(source_root):
                try:
                    guard_path(directory)
                    directory.rmdir()  # Only empty directories; never recursive deletion.
                    emit(f"REMOVED EMPTY {directory}")
                except (OSError, ValueError):
                    break
                directory = directory.parent
    emit(json.dumps(result, sort_keys=True))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--config", type=Path, help="Optional TOML configuration")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--tv", type=Path)
    parser.add_argument("--movies", type=Path)
    parser.add_argument("--min-size-mb", type=float, default=None, help="Minimum size in MiB (default: 100)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Perform the planned moves")
    mode.add_argument("--dry-run", action="store_true", help="Preview only (the default)")
    parser.add_argument("--cleanup-empty", action="store_true", default=None)
    parser.add_argument("--no-satellites", action="store_true")
    args = parser.parse_args(argv)
    try:
        settings = {}
        if args.config:
            with args.config.open("rb") as file:
                settings = tomllib.load(file)
        allowed = set(Config.__dataclass_fields__)
        if set(settings) - allowed:
            raise ValueError(f"Unknown configuration keys: {sorted(set(settings) - allowed)}")
        for name in ("source", "tv", "movies", "min_size_mb", "cleanup_empty"):
            value = getattr(args, name)
            if value is not None:
                settings[name] = value
        if args.no_satellites:
            settings["satellites"] = False
        for name in ("source", "tv", "movies"):
            if name not in settings:
                raise ValueError(f"Provide --{name} or configure '{name}'")
            settings[name] = Path(settings[name]).expanduser().absolute()
        for name in ("satellites", "cleanup_empty"):
            if name in settings and not isinstance(settings[name], bool):
                raise ValueError(f"{name} must be true or false")
        if "min_size_mb" in settings and (isinstance(settings["min_size_mb"], bool)
                                          or not isinstance(settings["min_size_mb"], (int, float))):
            raise ValueError("min_size_mb must be numeric")
        config = Config(**settings)
        result = execute(build_plan(config), config, apply=args.apply)
        return 1 if result["failed"] else 0
    except (OSError, ValueError, TypeError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    sys.exit(main())
