import contextlib
import io
from pathlib import Path
import tempfile
import unittest

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
            self.assertIn("undated_fs = '%t/Season %0s/%t S%0s E%0e'", target.read_text(encoding="utf-8"))

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
