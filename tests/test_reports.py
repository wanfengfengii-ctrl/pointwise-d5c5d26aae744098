from censoring import FitError, Observation, Study, ValidationError
from tests.common import AnalysisCase


class ReportTests(AnalysisCase):
    def test_split_and_repeat(self):
        self.prepare([1, 2, 3], [(1, 2, 4), (3, 3, 2)])
        whole = self.study.survival("c", [1, 2, 3], report_id="r")
        self.assertEqual(whole, self.study.survival("c", [1, 2, 3], report_id="r"))
        with Study() as other:
            other.import_observations([
                Observation("x", 1, 1, 2, 1), Observation("y", 1, 1, 2, 3),
                Observation("z", 1, 3, 3, 2)
            ])
            frozen = other.freeze("split", [1, 2, 3], ["x", "y", "z"])
            self.assertEqual(len(frozen.patterns), 2)
            other.fit("split")
            split = other.survival("split", [1, 2, 3], report_id="s")
        self.assertEqual([(r.lower, r.upper) for r in whole.ranges],
                         [(r.lower, r.upper) for r in split.ranges])

    def test_unready_fit(self):
        self.study.import_observations([
            Observation("a", 1, 1, 1, 1), Observation("b", 1, 2, 2, 3)
        ])
        self.study.freeze("c", [1, 2], ["a", "b"])
        with self.assertRaises(FitError):
            self.study.fit("c", max_iterations=0)
        with self.assertRaises(FitError):
            self.study.fit_result("c")
        with self.assertRaises(FitError):
            self.study.survival("c", [1], report_id="failed")
        with self.assertRaises(ValidationError):
            self.study.report("failed")
        self.study.fit("c")
        self.assertRanges(self.study.survival("c", [1], report_id="ok"), [(.25, .25)])

    def test_invalid_report_is_atomic_and_ids_are_fixed(self):
        self.prepare([1, 2, 3], [(1, 2, 4)])
        for points in ([], [1, 9], [float("inf")], [True]):
            with self.assertRaises(ValidationError):
                self.study.survival("c", points, report_id="r")
            with self.assertRaises(ValidationError):
                self.study.report("r")
        report = self.study.survival("c", [2, 1, 1], report_id="r")
        self.assertRanges(report, [(1, 1), (0, 1), (0, 1)])
        with self.assertRaises(ValidationError):
            self.study.survival("c", [1, 2], report_id="r")
        self.assertEqual(report, self.study.report("r"))

    def test_unknown_cohort_and_report(self):
        with self.assertRaises(ValidationError):
            self.study.fit("absent")
        with self.assertRaises(ValidationError):
            self.study.survival("absent", [1], report_id="r")
        with self.assertRaises(ValidationError):
            self.study.report("r")
