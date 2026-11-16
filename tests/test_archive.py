from pathlib import Path
import sqlite3
import tempfile
import unittest
from censoring import Observation, Study, ValidationError


class ArchiveTests(unittest.TestCase):
    def test_close_reopen(self):
        with tempfile.TemporaryDirectory(prefix="censoring-test-") as directory:
            path = Path(directory) / "study.sqlite"
            with Study(path) as study:
                study.import_observations([
                    Observation("a", 1, 1, 1, 1), Observation("b", 1, 2, 2, 3)
                ])
                study.freeze("old", [1, 2], ["a", "b"])
                fit = study.fit("old")
                report = study.survival("old", [1, 2], report_id="old-r")
                study.import_observations([
                    Observation("a", 2, 1, 1, 3), Observation("b", 2, 2, 2, 1)
                ])
            with Study(path) as reopened:
                self.assertEqual(reopened.fit_result("old"), fit)
                self.assertEqual(reopened.report("old-r"), report)
                self.assertEqual(reopened.cohort("old").observations[0].rev, 1)
                self.assertEqual(reopened.current("a").rev, 2)
                self.assertEqual(len(reopened.revisions("a")), 2)
                reopened.freeze("new", [1, 2], ["a", "b"])
                reopened.fit("new")
                new = reopened.survival("new", [1], report_id="new-r")
                self.assertAlmostEqual(float(new.ranges[0].lower), .75, delta=1e-8)
                self.assertEqual(reopened.survival("old", [1, 2], report_id="old-r"), report)
            with sqlite3.connect(path) as raw:
                self.assertEqual(raw.execute("PRAGMA user_version").fetchone()[0], 1)
                self.assertEqual(raw.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_unknown_schema_is_preserved(self):
        with tempfile.TemporaryDirectory(prefix="censoring-test-") as directory:
            path = Path(directory) / "other.sqlite"
            with sqlite3.connect(path) as raw:
                raw.execute("CREATE TABLE unrelated(value TEXT)")
                raw.execute("INSERT INTO unrelated VALUES('keep')")
            with self.assertRaises(ValidationError):
                Study(path)
            with sqlite3.connect(path) as raw:
                self.assertEqual(raw.execute("SELECT * FROM unrelated").fetchall(), [("keep",)])
                self.assertEqual(raw.execute("PRAGMA user_version").fetchone()[0], 0)
