import contextlib
import io
import json
import unittest
from censoring import Study
from censoring.cli import demonstration, execute, main


class CliTests(unittest.TestCase):
    def test_demo(self):
        result = demonstration()
        self.assertEqual(result["unresolved"]["ranges"][0]["lower"], "0")
        self.assertEqual(result["unresolved"]["ranges"][0]["upper"], "1")
        self.assertEqual(result["original"], result["old_report_after_correction"])

    def test_workflow_api(self):
        with Study() as study:
            results = execute(study, [
                {"op": "import", "observations": [
                    {"id": "a", "rev": 1, "lower": 1, "upper": 2, "count": 4}
                ]},
                {"op": "freeze", "cohort": "c", "support": [1, 2], "ids": ["a"]},
                {"op": "fit", "cohort": "c"},
                {"op": "survival", "cohort": "c", "cutoffs": [1], "report": "r"},
                {"op": "read_report", "report": "r"},
            ])
        self.assertEqual(results[-1]["result"], results[-2]["result"])
        self.assertEqual(results[-1]["result"]["ranges"][0]["upper"], "1")

    def test_cli_json_error_exit(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            status = main(["run", "samples/file-that-does-not-exist.json"])
        self.assertEqual(status, 2)
        self.assertIn("error", json.loads(stream.getvalue()))
