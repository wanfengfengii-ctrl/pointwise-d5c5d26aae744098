"""Likelihood fitting and durable cohort-bound publication."""
from dataclasses import dataclass
from decimal import Decimal
import json
from .errors import FitError, ValidationError
from .numerics import maximize
from .observations import encode


@dataclass(frozen=True)
class FitResult:
    cohort_id: str
    fingerprint: str
    mass: tuple[Decimal, ...]
    pattern_probabilities: tuple[Decimal, ...]
    log_likelihood: Decimal


def coverage(cohort):
    return [[int(j in pattern.indices) for j in range(len(cohort.support))]
            for pattern in cohort.patterns]


class Fitting:
    def __init__(self, connection, cohorts):
        self.db = connection
        self.cohorts = cohorts

    def fit(self, cohort_id, *, max_iterations=100):
        if type(max_iterations) is not int or not 0 <= max_iterations <= 300:
            raise ValidationError("max_iterations must be an integer in 0..300")
        cohort = self.cohorts.get(cohort_id)
        mass, probabilities, score = maximize(
            coverage(cohort), [p.count for p in cohort.patterns], max_iterations
        )
        body = encode({
            "mass": [str(p) for p in mass],
            "probabilities": [str(q) for q in probabilities],
            "log_likelihood": str(score),
        })
        with self.db:
            self.db.execute(
                "INSERT INTO fits VALUES(?,?,?) ON CONFLICT(cohort_id) "
                "DO UPDATE SET fingerprint=excluded.fingerprint,payload=excluded.payload",
                (cohort.id, cohort.fingerprint, body),
            )
        return FitResult(cohort.id, cohort.fingerprint, mass, probabilities, score)

    def get(self, cohort_id):
        cohort = self.cohorts.get(cohort_id)
        row = self.db.execute(
            "SELECT fingerprint,payload FROM fits WHERE cohort_id=?", (cohort_id,)
        ).fetchone()
        if row is None:
            raise FitError("cohort has no published fit")
        if row[0] != cohort.fingerprint:
            raise FitError("fit and cohort content do not match")
        body = json.loads(row[1])
        return FitResult(
            cohort.id, row[0], tuple(map(Decimal, body["mass"])),
            tuple(map(Decimal, body["probabilities"])), Decimal(body["log_likelihood"])
        )
