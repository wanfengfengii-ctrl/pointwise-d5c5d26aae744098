from dataclasses import FrozenInstanceError
from censoring import Observation, ValidationError
from tests.common import AnalysisCase


class RevisionTests(AnalysisCase):
    def initial(self):
        self.study.import_observations([
            Observation("a", 1, 1, 1, 1), Observation("b", 1, 2, 2, 3)
        ])
        self.study.freeze("old", [1, 2], ["b", "a"])
        self.study.fit("old")
        return self.study.survival("old", [1], report_id="old-report")

    def test_isolation(self):
        old = self.initial()
        snapshot = self.study.cohort("old")
        self.study.import_observations([
            Observation("a", 2, 1, 1, 3), Observation("b", 2, 2, 2, 1)
        ])
        self.study.freeze("new", [1, 2], ["a", "b"])
        self.study.fit("new")
        self.assertRanges(self.study.survival("new", [1], report_id="new-report"), [(.75, .75)])
        self.assertEqual(snapshot, self.study.cohort("old"))
        self.assertEqual(old, self.study.report("old-report"))
        self.assertRanges(self.study.survival("old", [1], report_id="old-extra"), [(.25, .25)])
        self.study.fit("old")
        self.assertEqual(old, self.study.survival("old", [1], report_id="old-report"))
        with self.assertRaises(FrozenInstanceError):
            snapshot.observations[0].count = 19

    def test_invalid_batch(self):
        old = self.initial()
        with self.assertRaises(ValidationError):
            self.study.import_observations([
                Observation("a", 2, 1, 1, 3), Observation("bad", 1, 2, 1, 1)
            ])
        self.assertEqual(self.study.current("a").rev, 1)
        self.assertEqual(self.study.report("old-report"), old)

    def test_conflict_rolls_back_earlier_write(self):
        self.initial()
        with self.assertRaises(ValidationError):
            self.study.import_observations([
                Observation("a", 2, 1, 1, 3), Observation("b", 1, 2, 2, 2)
            ])
        self.assertEqual(self.study.current("a").rev, 1)
        self.assertEqual([r.rev for r in self.study.revisions("a")], [1])

    def test_replay_low_revision_withdraw_and_restore(self):
        record = Observation("a", 2, 1, 2, 4)
        self.study.import_observations([record])
        self.assertEqual(self.study.import_observations([record])[0].rev, 2)
        self.study.import_observations([Observation("a", 1, 9, 9, 1)])
        self.assertEqual(self.study.current("a"), record)
        self.study.freeze("before", [1, 2], ["a"])
        self.study.fit("before")
        old = self.study.survival("before", [1], report_id="r")
        self.study.import_observations([Observation("a", 3, withdrawn=True)])
        with self.assertRaises(ValidationError):
            self.study.freeze("after", [1, 2], ["a"])
        self.study.import_observations([Observation("a", 4, 2, 2, 2)])
        self.study.freeze("after", [1, 2], ["a"])
        self.assertEqual(self.study.report("r"), old)
        self.assertEqual([r.rev for r in self.study.revisions("a")], [2, 3, 4])

    def test_validation_and_duplicate_batch(self):
        invalid = [
            Observation("", 1, 1, 1, 1), Observation("a", True, 1, 1, 1),
            Observation("a", 1, float("nan"), 1, 1), Observation("a", 1, 1, 1, True),
            Observation("a", 1, 1, 1, 21), Observation("a", 1, 1, 1, None),
            Observation("a", 1, 1, 1, 1, True), Observation("a", 1, None, None, 0),
        ]
        for record in invalid:
            with self.assertRaises(ValidationError):
                self.study.import_observations([record])
        with self.assertRaises(ValidationError):
            self.study.import_observations([
                Observation("a", 1, 1, 1, 1), Observation("a", 2, 1, 1, 2)
            ])
        with self.assertRaises(ValidationError):
            self.study.current("a")

    def test_large_revision_identity(self):
        high = 10 ** 40
        self.study.import_observations([Observation("a", high, 1, 1, 1)])
        self.study.import_observations([Observation("a", high + 1, 2, 2, 1)])
        self.study.import_observations([Observation("a", high - 1, 3, 3, 1)])
        self.assertEqual(self.study.current("a").rev, high + 1)
        self.assertEqual([r.rev for r in self.study.revisions("a")], [high, high + 1])
