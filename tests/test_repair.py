"""Regressions for the two public interval-censoring incidents.

The incident shapes come from PUBLIC_CHECKS.md. Expectations are
cross-checked against the independent rational certificates in
tests/oracle.py and against the frozen-binding rules in README.md.
"""
import tempfile
from fractions import Fraction as F
from pathlib import Path

from censoring import FitError, Observation, Study
from tests.common import AnalysisCase
from tests.oracle import certified_ranges


class IncidentRepairTests(AnalysisCase):
    def incident(self, label, support, rows):
        records = [Observation(label + str(i), 1, *row) for i, row in enumerate(rows)]
        self.study.import_observations(records)
        self.study.freeze(label, support, [r.id for r in records])
        fitted = self.study.fit(label)
        report = self.study.survival(label, support, report_id=label + "-report")
        return fitted, report

    def test_overlap_incident_restored(self):
        # Left- and right-censored counts overlap only at support 2:
        # every likelihood maximizer puts mass 1 there.
        fitted, report = self.incident("overlap", [1, 2, 3],
                                       [(None, 2, 4), (2, None, 4)])
        self.assertEqual(tuple(fitted.mass), (0, 1, 0))
        self.assertRanges(report, [(0, 0), (1, 1), (1, 1)])

    def test_unresolved_incident_restored(self):
        # One interval over [1,2]: the cumulative at 1 is unidentifiable
        # and must keep the full [0,1] range, not a collapsed split.
        fitted, report = self.incident("unresolved", [1, 2, 3], [(1, 2, 4)])
        self.assertRanges(report, [(0, 1), (1, 1), (1, 1)])

    def test_incidents_match_independent_certificates(self):
        examples = [
            ([1, 2, 3], [(None, 2, 4), (2, None, 4)], [0, 1, 0]),
            ([1, 2, 3], [(1, 2, 4)], [F(1, 2), F(1, 2), 0]),
            ([1, 2, 3], [(1, 2, 1), (1, 2, 3)], [F(1, 2), F(1, 2), 0]),
        ]
        for support, rows, mass in examples:
            expected = certified_ranges(support, rows, [F(x) for x in mass])
            with self.subTest(rows=rows), Study() as study:
                records = [Observation(str(i), 1, *row) for i, row in enumerate(rows)]
                study.import_observations(records)
                study.freeze("c", support, [r.id for r in records])
                study.fit("c")
                self.assertRanges(study.survival("c", support, report_id="r"), expected)

    def test_splitting_identical_intervals_keeps_result(self):
        # A count-4 interval and its 1+3 split are the same cohort content.
        whole_fit, whole = self.incident("whole", [1, 2, 3], [(1, 2, 4)])
        split_fit, split = self.incident("split", [1, 2, 3], [(1, 2, 1), (1, 2, 3)])
        self.assertEqual(whole_fit.pattern_probabilities,
                         split_fit.pattern_probabilities)
        self.assertEqual([(r.lower, r.upper) for r in whole.ranges],
                         [(r.lower, r.upper) for r in split.ranges])

    def test_zero_iterations_allow_stationary_face(self):
        # The symmetric zero-mass optimum is stationary at the uniform
        # face point, so a zero iteration budget still publishes it.
        self.study.import_observations([
            Observation("a", 1, 1, 2, 1), Observation("b", 1, 2, 3, 1),
            Observation("c", 1, 1, 1, 4), Observation("d", 1, 3, 3, 4),
        ])
        self.study.freeze("c", [1, 2, 3], ["a", "b", "c", "d"])
        fitted = self.study.fit("c", max_iterations=0)
        self.assertEqual(fitted.mass[1], 0)
        self.assertRanges(self.study.survival("c", [1, 2, 3], report_id="r"),
                          [(F(1, 2), F(1, 2)), (F(1, 2), F(1, 2)), (1, 1)])

    def test_zero_iterations_still_fail_nonstationary(self):
        self.study.import_observations([
            Observation("a", 1, 1, 1, 1), Observation("b", 1, 2, 2, 3),
        ])
        self.study.freeze("c", [1, 2], ["a", "b"])
        with self.assertRaises(FitError):
            self.study.fit("c", max_iterations=0)
        with self.assertRaises(FitError):
            self.study.fit_result("c")

    def test_correction_keeps_old_fit_and_report_after_reopen(self):
        with tempfile.TemporaryDirectory(prefix="censoring-repair-") as directory:
            path = Path(directory) / "study.sqlite"
            with Study(path) as study:
                study.import_observations([
                    Observation("left", 1, None, 2, 4),
                    Observation("right", 1, 2, None, 4),
                ])
                study.freeze("overlap", [1, 2, 3], ["left", "right"])
                fit = study.fit("overlap")
                report = study.survival("overlap", [1, 2, 3], report_id="overlap-r")
                study.import_observations([Observation("left", 2, 1, 1, 1)])
            with Study(path) as reopened:
                self.assertEqual(reopened.fit_result("overlap"), fit)
                self.assertEqual(reopened.report("overlap-r"), report)
                reopened.fit("overlap")
                self.assertEqual(reopened.report("overlap-r"), report)
                self.assertRanges(
                    reopened.survival("overlap", [1, 2, 3], report_id="overlap-extra"),
                    [(0, 0), (1, 1), (1, 1)])
                self.assertEqual(reopened.report("overlap-r"), report)
