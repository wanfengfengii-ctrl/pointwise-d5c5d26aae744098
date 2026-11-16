from fractions import Fraction as F
import random
from censoring import Observation, Study
from tests.common import AnalysisCase
from tests.oracle import certified_ranges


class CertificateTests(AnalysisCase):
    def test_hand_certificates(self):
        examples = [
            ([1, 2], [(1, 1, 1), (2, 2, 3)], [F(1, 4), F(3, 4)]),
            ([1, 2], [(1, 2, 4)], [F(1, 2), F(1, 2)]),
            ([1, 2, 3], [(None, 2, 4), (2, None, 4)], [0, 1, 0]),
            ([1, 2, 3], [(1, 2, 2), (2, 3, 3), (1, 1, 4), (3, 3, 1)],
             [F(4, 7), F(2, 21), F(1, 3)]),
            ([1, 2, 3], [(1, 2, 1), (2, 3, 1), (1, 1, 4), (3, 3, 4)],
             [F(1, 2), 0, F(1, 2)]),
            ([1, 2, 3, 4], [(1, 2, 2), (3, 3, 3)],
             [F(1, 5), F(1, 5), F(3, 5), 0]),
        ]
        for index, (support, rows, mass) in enumerate(examples):
            with self.subTest(example=index), Study() as study:
                expected = certified_ranges(support, rows, mass)
                records = [Observation(str(i), 1, *row) for i, row in enumerate(rows)]
                study.import_observations(records)
                study.freeze("c", support, [r.id for r in records])
                study.fit("c")
                self.assertRanges(study.survival("c", support, report_id="r"), expected)

    def test_partition_certificates(self):
        rng = random.Random(8147)
        accepted = 0
        while accepted < 24:
            n = rng.randrange(2, 7)
            integers = [rng.randrange(0, 4) for unused in range(n)]
            if not sum(integers):
                continue
            total = sum(integers)
            support = list(range(1, n + 1))
            patterns = {}
            for layer in range(rng.randrange(1, 4)):
                cuts = [0] + [i for i in range(1, n) if rng.randrange(2)] + [n]
                for lo, hi in zip(cuts, cuts[1:]):
                    count = sum(integers[lo:hi])
                    if count:
                        key = (support[lo], support[hi - 1])
                        patterns[key] = patterns.get(key, 0) + count
            if len(patterns) > 12 or max(patterns.values()) > 20:
                continue
            rows = [(lo, hi, count) for (lo, hi), count in sorted(patterns.items())]
            expected = certified_ranges(support, rows, [F(p, total) for p in integers])
            with self.subTest(case=accepted, rows=rows), Study() as study:
                records = [Observation(str(i), 1, *row) for i, row in enumerate(rows)]
                study.import_observations(records)
                study.freeze("c", support, [r.id for r in records])
                fitted = study.fit("c")
                self.assertEqual(fitted.fingerprint, study.cohort("c").fingerprint)
                self.assertRanges(study.survival("c", support, report_id="r"), expected)
            accepted += 1
