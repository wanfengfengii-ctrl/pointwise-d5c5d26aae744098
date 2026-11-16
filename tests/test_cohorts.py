from censoring import Observation, ValidationError
from tests.common import AnalysisCase


class CohortTests(AnalysisCase):
    def test_unknown(self):
        self.study.import_observations([Observation("a", 1, 1, 2, 3)])
        with self.assertRaises(ValidationError):
            self.study.freeze("c", [1, 2], ["a", "unknown"])
        with self.assertRaises(ValidationError):
            self.study.cohort("c")
        self.assertEqual(self.study.freeze("c", [1, 2], ["a"]).id, "c")

    def test_idempotence_and_conflict(self):
        self.study.import_observations([
            Observation("a", 1, 1, 1, 2), Observation("b", 1, 2, 2, 2)
        ])
        first = self.study.freeze("c", [1, 2], ["a", "b"])
        self.assertEqual(first, self.study.freeze("c", [1, 2], ["b", "a"]))
        with self.assertRaises(ValidationError):
            self.study.freeze("c", [1, 2, 3], ["a", "b"])
        self.assertEqual(self.study.cohort("c"), first)

    def test_limits_and_empty_intersection(self):
        self.study.import_observations([Observation("a", 1, 1, 2, 3)])
        for support, ids in (([], ["a"]), ([2, 1], ["a"]), ([1, 1], ["a"]),
                             ([1, 2], []), ([1, 2], ["a", "a"]),
                             ([3, 4], ["a"]), (list(range(7)), ["a"])):
            with self.assertRaises(ValidationError):
                self.study.freeze("c", support, ids)
        self.study.import_observations([Observation("b", 1, 1, 2, 18)])
        with self.assertRaises(ValidationError):
            self.study.freeze("c", [1, 2], ["a", "b"])
        self.study.freeze("c", [1, 2], ["a"])

    def test_twelve_pattern_limit(self):
        records = []
        for lo in range(1, 6):
            for hi in range(lo, 7):
                records.append(Observation(str(len(records)), 1, lo, hi, 1))
        self.study.import_observations(records[:13])
        with self.assertRaises(ValidationError):
            self.study.freeze("c", [1, 2, 3, 4, 5, 6], [r.id for r in records[:13]])
