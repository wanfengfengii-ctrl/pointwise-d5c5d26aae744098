import unittest
from censoring import Observation, Study


class AnalysisCase(unittest.TestCase):
    def setUp(self):
        self.study = Study()
        self.addCleanup(self.study.close)

    def prepare(self, support, rows, cohort="c"):
        records = [Observation(str(i), 1, lo, hi, count)
                   for i, (lo, hi, count) in enumerate(rows)]
        self.study.import_observations(records)
        frozen = self.study.freeze(cohort, support, [r.id for r in records])
        fitted = self.study.fit(cohort)
        return frozen, fitted

    def assertRanges(self, report, expected):
        self.assertEqual(len(report.ranges), len(expected))
        for actual, pair in zip(report.ranges, expected):
            self.assertAlmostEqual(float(actual.lower), float(pair[0]), delta=1e-8)
            self.assertAlmostEqual(float(actual.upper), float(pair[1]), delta=1e-8)
