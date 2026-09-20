"""Regression and failure-injection tests; use only isolated temporary files."""
from dataclasses import replace
import contextlib
import io
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import turbo_sort as ts


class ParsingTests(unittest.TestCase):
    def test_movie_ending_in_year(self):
        media = ts.parse_media(Path("Movie.2020.mkv"))
        self.assertEqual(ts.format_media(media, "%t (%y)"), Path("Movie (2020)"))

    def test_movie_year_and_modern_quality(self):
        media = ts.parse_media(Path("Spider-Man.2024.2160p.HEVC.mkv"))
        self.assertEqual((media.title, media.year, media.quality), ("Spider-Man", 2024, "2160p"))

    def test_quality_at_end(self):
        self.assertEqual(ts.parse_media(Path("Movie.2020.1080p.mkv")).quality, "1080p")

    def test_underscore_separators(self):
        self.assertEqual(ts.parse_media(Path("The_Show_S01E02_1080p.mkv")).episodes, (2,))

    def test_season_and_multi_episode(self):
        media = ts.parse_media(Path("The.Office.S06E03E04E05.mkv"))
        self.assertEqual(ts.format_media(media, "%t S%0s E%0e"), Path("The Office S06 E03E04E05"))
        self.assertEqual(ts.format_media(media, "%e"), Path("3E4E5"))

    def test_x_style(self):
        for name in ("Show.1x01.mkv", "Show.10x101.mkv"):
            with self.subTest(name=name):
                self.assertEqual(ts.parse_media(Path(name)).kind, "tv")

    def test_numeric_months(self):
        media = ts.parse_media(Path("News.2024.03.05.mkv"))
        self.assertEqual(ts.format_media(media, "%m-%0m-%d-%0d-%sm-%fm"), Path("3-03-5-05-Mar-March"))

    def test_invalid_dates_rejected(self):
        for day in ("2023.02.29", "2024.13.01", "2024.00.01", "2024.04.31"):
            with self.subTest(day=day), self.assertRaises(ValueError):
                ts.parse_media(Path(f"News.{day}.mkv"))

    def test_leap_day(self):
        self.assertEqual(ts.parse_media(Path("News.2024.02.29.mkv")).aired.day, 29)

    def test_hash_uses_parent(self):
        media = ts.parse_media(Path("Movie.2020") / ("a" * 32 + ".mkv"))
        self.assertEqual(media.title, "Movie")

    def test_hash_requires_entire_name(self):
        media = ts.parse_media(Path("Other.2000") / ("a" * 32 + ".Movie.2020.mkv"))
        self.assertEqual(media.year, 2020)
        self.assertIn("Movie", media.title)

    def test_title_preserved(self):
        for title in ("Spider-Man", "CSI.US", "Amélie", "2001.A.Space.Odyssey"):
            with self.subTest(title=title):
                self.assertEqual(ts.parse_media(Path(f"{title}.2020.mkv")).title, title.replace(".", " "))

    def test_ambiguous_names_rejected(self):
        for name in ("Unknown.mkv", "Show.101.mkv", "Movie.1080p.mkv", "S01E01.mkv"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                ts.parse_media(Path(name))

    def test_template_validation(self):
        for template in ("../%t", "/%t", "C:\\%t", "%t/%", "%t/%0", "%z", "%t//%y"):
            with self.subTest(template=template), self.assertRaises(ValueError):
                ts.validate_template(template)

    def test_missing_quality_not_silently_discarded(self):
        with self.assertRaisesRegex(ValueError, "missing field"):
            ts.format_media(ts.parse_media(Path("Movie.2020.mkv")), "%q/%t")

    def test_windows_templates_and_reserved_names(self):
        media = ts.parse_media(Path("CON.2020.mkv"))
        self.assertEqual(ts.format_media(media, "%t\\%y"), Path("_CON") / "2020")

    def test_percent_literal(self):
        self.assertEqual(ts.format_media(ts.parse_media(Path("Movie.2020.mkv")), "%% %t"), Path("% Movie"))

    def test_episode_ranges_not_truncated(self):
        for name in ("Show.S01E01-E03.mkv", "Show.1x01-03.mkv"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                ts.parse_media(Path(name))

    def test_underscore_movie_year_quality(self):
        media = ts.parse_media(Path("My_Movie_2020_2160p.mkv"))
        self.assertEqual((media.title, media.year, media.quality), ("My Movie", 2020, "2160p"))

    def test_2000_generated_filenames(self):
        rng = random.Random(8675309)
        for _ in range(2000):
            season, episode = rng.randint(0, 99), rng.randint(0, 999)
            name = f"Example.Show.S{season:02}E{episode:02}.mkv"
            media = ts.parse_media(Path(name))
            self.assertEqual((media.season, media.episodes), (season, (episode,)))
            self.assertEqual(ts.format_media(media, "%0s-%0e"), Path(f"{season:02}-{episode:02}"))


class FileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="turbo-sort-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.config = ts.Config(self.source, self.root / "tv", self.root / "movies", min_size_mb=0)

    def write(self, name, content=b"video content", *, parent=None):
        path = (parent or self.source) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def run_plan(self, *, apply=True, config=None):
        config = config or self.config
        plan = ts.build_plan(config)
        return ts.execute(plan, config, apply=apply, emit=lambda _: None)

    def test_preview_creates_no_files(self):
        video = self.write("Movie.2020.mkv")
        before = sorted(str(p) for p in self.root.rglob("*"))
        result = self.run_plan(apply=False, config=replace(self.config, cleanup_empty=True))
        self.assertEqual(before, sorted(str(p) for p in self.root.rglob("*")))
        self.assertEqual(result["moved"], 0)
        self.assertEqual(video.read_bytes(), b"video content")

    def test_move_and_rerun(self):
        video = self.write("Movie.2020.mkv")
        self.assertEqual(self.run_plan()["moved"], 1)
        self.assertFalse(video.exists())
        target = self.config.movies / "Movie (2020).mkv"
        self.assertEqual(target.read_bytes(), b"video content")
        self.assertEqual(self.run_plan()["moved"], 0)
        self.assertEqual(target.read_bytes(), b"video content")

    def test_existing_destination_preserves_source_and_subtitles(self):
        video = self.write("Movie.2020.mkv", b"new version")
        sub = self.write("Movie.2020.en.srt", b"English")
        target = self.write("Movie (2020).mkv", b"existing version", parent=self.config.movies)
        result = self.run_plan(config=replace(self.config, cleanup_empty=True))
        self.assertEqual(result["moved"], 0)
        self.assertEqual(video.read_bytes(), b"new version")
        self.assertEqual(target.read_bytes(), b"existing version")
        self.assertEqual(sub.read_bytes(), b"English")

    def test_two_sources_same_destination_both_retained(self):
        a = self.write("Movie.2020.720p.mkv", b"A")
        b = self.write("Movie.2020.1080p.mkv", b"B")
        self.assertEqual(self.run_plan()["moved"], 0)
        self.assertEqual((a.read_bytes(), b.read_bytes()), (b"A", b"B"))

    def test_subtitle_languages_preserved(self):
        self.write("Movie.2020.mkv")
        self.write("Movie.2020.en.srt", b"English")
        self.write("Movie.2020.fr.forced.SRT", b"French")
        self.write("Movie.2020.idx", b"index")
        self.assertEqual(self.run_plan()["moved"], 4)
        self.assertEqual((self.config.movies / "Movie (2020).en.srt").read_bytes(), b"English")
        self.assertEqual((self.config.movies / "Movie (2020).fr.forced.srt").read_bytes(), b"French")

    def test_satellite_collision_does_not_loop(self):
        self.write("Movie.2020.mkv")
        sub = self.write("Movie.2020.en.srt", b"new")
        old = self.write("Movie (2020).en.srt", b"old", parent=self.config.movies)
        self.assertEqual(self.run_plan()["moved"], 1)
        self.assertEqual((sub.read_bytes(), old.read_bytes()), (b"new", b"old"))

    def test_prefix_related_files_are_not_deleted(self):
        self.write("Movie.2020.mkv")
        other = self.write("Movie.2020.notes.txt", b"important")
        self.run_plan(config=replace(self.config, cleanup_empty=True))
        self.assertEqual(other.read_bytes(), b"important")

    def test_cleanup_only_empty_folders(self):
        self.write("nested/inner/Movie.2020.mkv")
        self.run_plan(config=replace(self.config, cleanup_empty=True))
        self.assertFalse((self.source / "nested").exists())
        self.assertTrue(self.source.is_dir())

    def test_cleanup_off_preserves_empty_folder(self):
        self.write("nested/Movie.2020.mkv")
        self.run_plan()
        self.assertTrue((self.source / "nested").is_dir())

    def test_missing_source_rejected(self):
        with self.assertRaises(ValueError):
            ts.build_plan(replace(self.config, source=self.root / "missing"))

    def test_overlapping_roots_rejected(self):
        for target in (self.source, self.source / "sorted", self.root):
            with self.subTest(target=target), self.assertRaises(ValueError):
                ts.build_plan(replace(self.config, tv=target))

    def test_minimum_size(self):
        self.write("Movie.2020.mkv")
        self.assertEqual(self.run_plan(config=replace(self.config, min_size_mb=1))["moved"], 0)

    def test_changed_source_after_planning_retained(self):
        video = self.write("Movie.2020.mkv")
        plan = ts.build_plan(self.config)
        video.write_bytes(b"changed during download")
        result = ts.execute(plan, self.config, apply=True, emit=lambda _: None)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(video.read_bytes(), b"changed during download")

    def test_publish_failure_retains_source_and_removes_partial(self):
        video = self.write("Movie.2020.mkv")
        with patch.object(ts, "publish", side_effect=OSError("simulated disk failure")):
            result = self.run_plan()
        self.assertEqual(result["failed"], 1)
        self.assertEqual(video.read_bytes(), b"video content")
        self.assertEqual(list(self.root.rglob("*.partial")), [])

    def test_corrupted_copy_retains_source(self):
        video = self.write("Movie.2020.mkv")
        with patch.object(ts, "digest", return_value=b"wrong checksum"):
            result = self.run_plan()
        self.assertEqual(result["failed"], 1)
        self.assertTrue(video.exists())
        self.assertEqual(list(self.root.rglob("*.partial")), [])
        self.assertFalse((self.config.movies / "Movie (2020).mkv").exists())

    def test_destination_created_after_plan_retained(self):
        video = self.write("Movie.2020.mkv")
        plan = ts.build_plan(self.config)
        target = self.write("Movie (2020).mkv", b"another process", parent=self.config.movies)
        result = ts.execute(plan, self.config, apply=True, emit=lambda _: None)
        self.assertEqual(result["failed"], 1)
        self.assertTrue(video.exists())
        self.assertEqual(target.read_bytes(), b"another process")

    def test_exclusive_publish_race(self):
        video = self.write("Movie.2020.mkv")
        original = ts.publish

        def race(staged, target):
            target.write_bytes(b"race winner")
            original(staged, target)

        with patch.object(ts, "publish", side_effect=race):
            result = self.run_plan()
        self.assertEqual(result["failed"], 1)
        self.assertTrue(video.exists())
        self.assertEqual((self.config.movies / "Movie (2020).mkv").read_bytes(), b"race winner")

    def test_parent_failure_keeps_satellites(self):
        self.write("Movie.2020.mkv")
        sub = self.write("Movie.2020.srt")
        with patch.object(ts, "publish", side_effect=PermissionError("denied")):
            result = self.run_plan()
        self.assertEqual(result["failed"], 1)
        self.assertTrue(sub.exists())

    def test_source_unlink_failure_keeps_both_copies(self):
        video = self.write("Movie.2020.mkv")
        real_unlink = Path.unlink

        def fail_source(path, *args, **kwargs):
            if path == video:
                raise PermissionError("locked source")
            return real_unlink(path, *args, **kwargs)

        with patch.object(Path, "unlink", fail_source):
            result = self.run_plan()
        self.assertEqual(result["failed"], 1)
        self.assertEqual(video.read_bytes(), b"video content")
        self.assertEqual((self.config.movies / "Movie (2020).mkv").read_bytes(), b"video content")

    def test_case_collision(self):
        video = self.write("Movie.2020.mkv")
        self.write("movie (2020).MKV", parent=self.config.movies)
        self.assertEqual(self.run_plan()["moved"], 0)
        self.assertTrue(video.exists())

    def test_linked_video_skipped(self):
        outside = self.write("outside.mkv", parent=self.root)
        linked = self.source / "Movie.2020.mkv"
        try:
            linked.symlink_to(outside)
        except OSError:
            self.skipTest("Host cannot create symlinks")
        self.assertEqual(self.run_plan()["moved"], 0)
        self.assertTrue(outside.exists())

    def test_cli_preview_apply_repeat(self):
        self.write("Movie.2020.mkv")
        cmd = [sys.executable, str(Path(ts.__file__)), "--source", str(self.source),
               "--tv", str(self.config.tv), "--movies", str(self.config.movies), "--min-size-mb", "0"]
        outputs = []
        for flags in ([], ["--apply"], ["--apply"]):
            proc = subprocess.run(cmd + flags, capture_output=True, text=True, check=True)
            outputs.append(json.loads(proc.stdout.splitlines()[-1]))
        self.assertEqual([r["moved"] for r in outputs], [0, 1, 0])

    def test_toml_config(self):
        self.write("Movie.2020.mkv")
        config_file = self.root / "config.toml"
        config_file.write_text(f"source = '{self.source}'\ntv = '{self.config.tv}'\nmovies = '{self.config.movies}'\nmin_size_mb = 0\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(ts.main(["--config", str(config_file)]), 0)
        self.assertIn("PREVIEW", out.getvalue())

    def test_bad_config_errors_cleanly(self):
        config_file = self.root / "config.toml"
        config_file.write_text("overwrite = true\n", encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            ts.main(["--config", str(config_file)])
        self.assertEqual(raised.exception.code, 2)

    def test_read_failure_reported_as_failure(self):
        self.write("Movie.2020.mkv")
        with patch.object(ts, "stamp", side_effect=PermissionError("denied")):
            result = self.run_plan()
        self.assertEqual(result["failed"], 1)

    def test_change_during_copy_retains_source(self):
        video = self.write("Movie.2020.mkv")
        real_digest = ts.digest

        def change(path):
            video.write_bytes(b"new content from downloader")
            return real_digest(path)

        with patch.object(ts, "digest", side_effect=change):
            result = self.run_plan()
        self.assertEqual(result["failed"], 1)
        self.assertEqual(video.read_bytes(), b"new content from downloader")

    def test_import_does_not_walk_or_move(self):
        proc = subprocess.run([sys.executable, "-c", "from unittest.mock import patch; "
                               "p=patch('os.walk', side_effect=AssertionError('walked')); "
                               "p.start(); import turbo_sort; print('safe import')"],
                              cwd=Path(ts.__file__).parent, capture_output=True, text=True, check=True)
        self.assertEqual(proc.stdout.strip(), "safe import")

    def test_nonfinite_size_rejected(self):
        for size in (-1, float("nan"), float("inf")):
            with self.subTest(size=size), self.assertRaises(ValueError):
                ts.build_plan(replace(self.config, min_size_mb=size))

    def test_disabled_satellites_remain(self):
        self.write("Movie.2020.mkv")
        sub = self.write("Movie.2020.en.srt")
        self.assertEqual(self.run_plan(config=replace(self.config, satellites=False))["moved"], 1)
        self.assertTrue(sub.exists())

    def test_disk_full_simulation(self):
        video = self.write("Movie.2020.mkv")
        with patch.object(ts.os, "fsync", side_effect=OSError("disk full")):
            result = self.run_plan()
        self.assertEqual(result["failed"], 1)
        self.assertEqual(video.read_bytes(), b"video content")
        self.assertEqual(list(self.root.rglob("*.partial")), [])


if __name__ == "__main__":
    unittest.main()
