#!/usr/bin/env python3
"""Interactive, safe configuration wizard for Turbo Sort.

This program writes config.toml; it never edits turbo_sort.py and never moves files.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
import tomllib

import turbo_sort


def ask(prompt: str, default: str | None = None, *, input_fn=input) -> str:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        value = input_fn(f"{prompt}{suffix}: ").strip()
        if value:
            return value
        if default is not None:
            return default
        print("Please enter a value.")


def ask_yes_no(prompt: str, default: bool, *, input_fn=input) -> bool:
    answer = ask(prompt + " (y/n)", "y" if default else "n", input_fn=input_fn).lower()
    while answer not in {"y", "n", "yes", "no"}:
        answer = ask("Please enter y or n", input_fn=input_fn).lower()
    return answer in {"y", "yes"}


def ask_choice(prompt: str, choices: list[tuple[str, str]], default: str, *, input_fn=input) -> str:
    print(prompt)
    for key, label in choices:
        print(f"  {key}. {label}")
    while True:
        answer = ask("Choose", default, input_fn=input_fn)
        for key, _ in choices:
            if answer == key:
                return key
        print("Please choose one of the listed numbers.")


def build_config(input_fn=input) -> dict[str, object]:
    source = Path(ask("Completed-download folder", input_fn=input_fn)).expanduser().absolute()
    tv = Path(ask("TV destination folder", input_fn=input_fn)).expanduser().absolute()
    movies = Path(ask("Movie destination folder", input_fn=input_fn)).expanduser().absolute()
    minimum = ask("Minimum video size in MiB", "100", input_fn=input_fn)
    try:
        min_size = float(minimum)
        if min_size < 0:
            raise ValueError
    except ValueError:
        raise ValueError("Minimum size must be a nonnegative number") from None

    padded = ask_choice("How should season and episode numbers look?", [
        ("1", "Padded: S03 E04"), ("2", "Unpadded: S3 E4")], "1", input_fn=input_fn)
    season_word = ask_choice("How should the season folder be named?", [
        ("1", "Season 3"), ("2", "S03")], "1", input_fn=input_fn)
    satellites = ask_yes_no("Move matching subtitles", True, input_fn=input_fn)
    cleanup = ask_yes_no("Remove empty source folders after successful moves", False, input_fn=input_fn)

    season = "%0s" if padded == "1" else "%s"
    episode = "%0e" if padded == "1" else "%e"
    folder = f"Season {season}" if season_word == "1" else f"S{season}"
    config = {
        "source": source,
        "tv": tv,
        "movies": movies,
        "min_size_mb": min_size,
        "satellites": satellites,
        "cleanup_empty": cleanup,
        "undated_fs": f"%t/{folder}/%t S{season} E{episode}",
        "dated_fs": "%t/%t %sm %0d %y",
        "movie_fs": "%t (%y)",
    }
    # Destinations may not exist yet, and a user may be preparing a config
    # before the downloader creates its folder. Validate the parts that do not
    # require touching the media tree; the sorter performs full validation when
    # it is run.
    for template in (config["undated_fs"], config["dated_fs"], config["movie_fs"]):
        turbo_sort.validate_template(str(template))
    roots = [Path(config[name]).resolve() for name in ("source", "tv", "movies")]
    if any(a == b or a.is_relative_to(b) or b.is_relative_to(a)
           for index, a in enumerate(roots) for b in roots[index + 1:]):
        raise ValueError("Source and destination folders must not overlap")
    return config


def toml_value(value: object) -> str:
    if isinstance(value, Path):
        value = str(value)
    if isinstance(value, str):
        # JSON string escaping also works for TOML basic strings. Keep Unicode
        # literal to avoid JSON surrogate pairs, which TOML does not accept.
        return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007f")
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return repr(value)


def render(config: dict[str, object]) -> str:
    lines = [
        "# Created by turbo_setup.py. Edit this file or run the wizard again.",
        "# Turbo Sort previews by default; add --apply only after reviewing the preview.",
    ]
    for key in ("source", "tv", "movies", "min_size_mb", "satellites", "cleanup_empty",
                "undated_fs", "dated_fs", "movie_fs"):
        lines.append(f"{key} = {toml_value(config[key])}")
    return "\n".join(lines) + "\n"


def write_config(config: dict[str, object], target: Path) -> Path:
    content = render(config)
    tomllib.loads(content)  # Validate before touching an existing config or backup.
    target = target.expanduser().absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.copy2(target, target.with_suffix(target.suffix + ".bak"))
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent,
                                     prefix=f".{target.name}.", suffix=".tmp", delete=False) as file:
        temporary = Path(file.name)
        file.write(content)
        file.flush()
    temporary.replace(target)
    return target


def sample(config: dict[str, object]) -> str:
    media = turbo_sort.parse_media(Path("Example.Show.S03E04.mkv"))
    relative = turbo_sort.format_media(media, str(config["undated_fs"]))
    return str(Path(config["tv"]) / (str(relative) + ".mkv"))


def main(argv: list[str] | None = None, *, input_fn=input, output_fn=print) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("config.toml"),
                        help="Configuration file to write (default: config.toml)")
    args = parser.parse_args(argv)
    try:
        config = build_config(input_fn=input_fn)
        output_fn("\nPreview using those choices:")
        output_fn(f"  Example.Show.S03E04.mkv -> {sample(config)}")
        if not ask_yes_no("Save this configuration", True, input_fn=input_fn):
            output_fn("Nothing was changed.")
            return 0
        target = write_config(config, args.output)
        output_fn(f"Saved {target}")
        output_fn("Run a preview with: python turbo_sort.py --config " + str(target))
        output_fn("Add --apply only after reviewing the preview.")
        return 0
    except (OSError, ValueError) as exc:
        output_fn(f"Setup failed: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
