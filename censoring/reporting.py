"""Publish cumulative probability bounds, retaining nonidentifiability."""
from dataclasses import dataclass
from decimal import Decimal, localcontext
import json
from .errors import ValidationError
from .fitting import coverage
from .numerics import PRECISION
from .observations import encode, name, number


@dataclass(frozen=True)
class ProbabilityRange:
    cutoff: float
    lower: Decimal
    upper: Decimal


@dataclass(frozen=True)
class Report:
    id: str
    cohort_id: str
    fingerprint: str
    ranges: tuple[ProbabilityRange, ...]


class Reporting:
    def __init__(self, connection, cohorts, fitting):
        self.db = connection
        self.cohorts = cohorts
        self.fitting = fitting

    def survival(self, cohort_id, cutoffs, *, report_id):
        name(report_id)
        cohort = self.cohorts.get(cohort_id)
        points = tuple(number(point) for point in cutoffs)
        if not points or any(point not in cohort.support for point in points):
            raise ValidationError("cutoffs must be a nonempty list of support points")
        fitted = self.fitting.get(cohort_id)
        extrema = (fitted.mass,)
        bounds = []
        with localcontext() as context:
            context.prec = PRECISION
            for point in points:
                end = cohort.support.index(point) + 1
                values = [sum(vertex[:end], Decimal(0)) for vertex in extrema]
                lower = max(Decimal(0), min(Decimal(1), min(values)))
                upper = max(Decimal(0), min(Decimal(1), max(values)))
                bounds.append(ProbabilityRange(point, lower, upper))
        payload = encode({
            "cutoffs": list(points),
            "ranges": [[str(item.lower), str(item.upper)] for item in bounds],
        })
        with self.db:
            previous = self.db.execute(
                "SELECT cohort_id,fingerprint,payload FROM reports WHERE id=?", (report_id,)
            ).fetchone()
            expected = (cohort.id, cohort.fingerprint, payload)
            if previous is not None and tuple(previous) != expected:
                raise ValidationError("report ID already binds a different request or result")
            self.db.execute(
                "INSERT OR IGNORE INTO reports VALUES(?,?,?,?)",
                (report_id, cohort.id, cohort.fingerprint, payload),
            )
        return Report(report_id, cohort.id, cohort.fingerprint, tuple(bounds))

    def get(self, report_id):
        name(report_id)
        row = self.db.execute(
            "SELECT cohort_id,fingerprint,payload FROM reports WHERE id=?", (report_id,)
        ).fetchone()
        if row is None:
            raise ValidationError("unknown report")
        body = json.loads(row[2])
        ranges = tuple(ProbabilityRange(point, Decimal(pair[0]), Decimal(pair[1]))
                       for point, pair in zip(body["cutoffs"], body["ranges"]))
        return Report(report_id, row[0], row[1], ranges)
