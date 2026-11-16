from fractions import Fraction as F
from decimal import Decimal, localcontext
from censoring import Observation, Study, ValidationError
from tests.common import AnalysisCase


class AnalysisTests(AnalysisCase):
    def test_complete(self):
        self.prepare([1, 2], [(1, 1, 1), (2, 2, 3)])
        self.assertRanges(self.study.survival("c", [1, 2], report_id="r"),
                          [(F(1, 4), F(1, 4)), (1, 1)])

    def test_nonidentifiable(self):
        self.prepare([1, 2], [(1, 2, 4)])
        self.assertRanges(self.study.survival("c", [1, 2], report_id="r"), [(0, 1), (1, 1)])

    def test_overlap_boundary(self):
        _, fitted = self.prepare([1, 2, 3], [(None, 2, 4), (2, None, 4)])
        self.assertEqual(tuple(fitted.mass), (0, 1, 0))
        self.assertRanges(self.study.survival("c", [1, 2, 3], report_id="r"),
                          [(0, 0), (1, 1), (1, 1)])

    def test_interior_overlapping_intervals(self):
        self.prepare([1, 2, 3], [(1, 2, 2), (2, 3, 3), (1, 1, 4), (3, 3, 1)])
        self.assertRanges(self.study.survival("c", [1, 2, 3], report_id="r"),
                          [(F(4, 7), F(4, 7)), (F(2, 3), F(2, 3)), (1, 1)])

    def test_strict_zero_mass(self):
        _, fitted = self.prepare([1, 2, 3], [(1, 2, 1), (2, 3, 1), (1, 1, 4), (3, 3, 4)])
        self.assertEqual(fitted.mass[1], 0)
        self.assertRanges(self.study.survival("c", [1, 2, 3], report_id="r"),
                          [(.5, .5), (.5, .5), (1, 1)])

    def test_partial_identification(self):
        self.prepare([1, 2, 3, 4], [(1, 2, 2), (3, 3, 3)])
        self.assertRanges(self.study.survival("c", [1, 2, 3, 4], report_id="r"),
                          [(0, .4), (.4, .4), (1, 1), (1, 1)])

    def test_single_support(self):
        self.prepare([7], [(None, None, 20)])
        self.assertRanges(self.study.survival("c", [7], report_id="r"), [(1, 1)])

    def test_relabel_preserves_geometry(self):
        rows = [(1, 2, 2), (3, 3, 3)]
        self.prepare([1, 2, 3], rows)
        original = self.study.survival("c", [1, 2, 3], report_id="r")
        with Study() as other:
            other.import_observations([
                Observation("x", 1, -5, 8, 2), Observation("y", 1, 100, 100, 3)
            ])
            other.freeze("renamed", [-5, 8, 100], ["x", "y"])
            other.fit("renamed")
            renamed = other.survival("renamed", [-5, 8, 100], report_id="r")
        self.assertEqual([(x.lower, x.upper) for x in original.ranges],
                         [(x.lower, x.upper) for x in renamed.ranges])

    def test_iteration_argument_validation(self):
        self.prepare([1, 2], [(1, 1, 1), (2, 2, 3)])
        for value in (-1, True, 301, 1.5):
            with self.assertRaises(ValidationError):
                self.study.fit("c", max_iterations=value)

    def test_irrational_interior(self):
        self.prepare([1, 2, 3], [(1, 1, 1), (2, 2, 1), (3, 3, 1), (1, 2, 1), (2, 3, 1)])
        with localcontext() as context:
            context.prec = 60
            x = (Decimal(5) - Decimal(5).sqrt()) / 10
            self.assertRanges(self.study.survival("c", [1, 2, 3], report_id="r"),
                              [(x, x), (1 - x, 1 - x), (1, 1)])
