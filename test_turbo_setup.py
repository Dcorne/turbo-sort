import contextlib
import io
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import patch

import turbo_setup


class SetupTests(unittest.TestCase):
    def answers(self, *values):
        iterator = iter(values)
        return lambda _: next(iterator)

    def test_builds_padded_season_template(self):
        config = turbo_setup.build_config(self.answers(
            "downloads", "tv", "movies", "0", "1", "1", "y", "n"))
        self.assertEqual(config["undated_fs"], "%t/Season %0s/%t S%0s E%0e")

    def test_builds_unpadded_s_template(self):
        config = turbo_setup.build_config(self.answers(
            "downloads", "tv", "movies", "100", "2", "2", "n", "y"))
        self.assertEqual(config["undated_fs"], "%t/S%s/%t S%s E%e")
        self.assertFalse(config["satellites"])
        self.assertTrue(config["cleanup_empty"])

    def test_render_is_valid_toml_and_writes_backup(self):
        config = turbo_setup.build_config(self.answers(
            "downloads", "tv", "movies", "100", "1", "1", "y", "n"))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "config.toml"
            target.write_text("old = true\n", encoding="utf-8")
            turbo_setup.write_config(config, target)
            self.assertTrue(target.with_suffix(".toml.bak").exists())
            loaded = tomllib.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(loaded["undated_fs"], config["undated_fs"])

    def test_strings_round_trip_through_toml(self):
        for value in (Path("O'Brien/Downloads"), Path('Media/Amélie 🎬'),
                      'a "quoted" title', 'back\\slash', 'control\t\n\x7f'):
            with self.subTest(value=value):
                loaded = tomllib.loads('value = ' + turbo_setup.toml_value(value))
                self.assertEqual(loaded['value'], str(value))

    def test_apostrophe_paths_survive_saved_config(self):
        with contextlib.redirect_stdout(io.StringIO()):
            config = turbo_setup.build_config(self.answers(
                "O'Brien/downloads", "O'Brien/tv", "O'Brien/movies",
                "0", "1", "1", "y", "n"))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'config.toml'
            turbo_setup.write_config(config, target)
            loaded = tomllib.loads(target.read_text(encoding='utf-8'))
            for key in ('source', 'tv', 'movies'):
                self.assertEqual(Path(loaded[key]), config[key])

    def test_invalid_render_preserves_config_and_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'config.toml'
            backup = target.with_suffix('.toml.bak')
            target.write_text('old = true\n', encoding='utf-8')
            backup.write_text('older = true\n', encoding='utf-8')
            with patch.object(turbo_setup, 'render', return_value="source = 'O''Brien'"), \
                    self.assertRaises(tomllib.TOMLDecodeError):
                turbo_setup.write_config({}, target)
            self.assertEqual(target.read_text(encoding='utf-8'), 'old = true\n')
            self.assertEqual(backup.read_text(encoding='utf-8'), 'older = true\n')

    def test_cancel_does_not_write(self):
        answers = self.answers("downloads", "tv", "movies", "100", "1", "1", "y", "n", "n")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "config.toml"
            output = io.StringIO()
            self.assertEqual(turbo_setup.main(["--output", str(target)], input_fn=answers,
                                               output_fn=output.write), 0)
            self.assertFalse(target.exists())
            self.assertIn("Nothing was changed", output.getvalue())


if __name__ == "__main__":
    unittest.main()
