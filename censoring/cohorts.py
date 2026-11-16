"""Frozen, content-bound cohorts; later current revisions are irrelevant."""
from dataclasses import asdict, dataclass
import hashlib
import json
from .errors import ValidationError
from .observations import Observation, encode, name, number


@dataclass(frozen=True)
class Pattern:
    indices: tuple[int, ...]
    count: int


@dataclass(frozen=True)
class Cohort:
    id: str
    support: tuple[float, ...]
    observations: tuple[Observation, ...]
    patterns: tuple[Pattern, ...]
    fingerprint: str


def payload_for(support, observations):
    return {
        "support": list(support),
        "observations": [asdict(record) for record in observations],
    }


def decode(cohort_id, payload, fingerprint):
    body = json.loads(payload)
    support = tuple(body["support"])
    records = tuple(Observation(**r) for r in body["observations"])
    counts = {}
    for record in records:
        indices = tuple(i for i, point in enumerate(support)
                        if (record.lower is None or record.lower <= point)
                        and (record.upper is None or point <= record.upper))
        if not indices:
            raise ValidationError("observation misses all support points")
        counts[indices] = counts.get(indices, 0) + record.count
    if len(counts) > 12 or any(count > 20 for count in counts.values()):
        raise ValidationError("at most 12 patterns, each with total count at most 20")
    patterns = tuple(Pattern(indices, count) for indices, count in sorted(counts.items()))
    return Cohort(cohort_id, support, records, patterns, fingerprint)


class Cohorts:
    def __init__(self, connection, observations):
        self.db = connection
        self.observations = observations

    def freeze(self, cohort_id, support, observation_ids):
        name(cohort_id)
        points = tuple(number(point) for point in support)
        if not 1 <= len(points) <= 6 or any(a >= b for a, b in zip(points, points[1:])):
            raise ValidationError("need 1..6 strictly increasing support points")
        ids = tuple(name(value) for value in observation_ids)
        if not ids or len(ids) != len(set(ids)):
            raise ValidationError("need distinct, explicitly selected observation IDs")
        with self.db:
            records = tuple(self.observations.current(value) for value in sorted(ids))
            if any(record.withdrawn for record in records):
                raise ValidationError("cannot freeze a withdrawn observation")
            payload = encode(payload_for(points, records))
            digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            result = decode(cohort_id, payload, digest)
            old = self.db.execute(
                "SELECT payload FROM cohorts WHERE id=?", (cohort_id,)
            ).fetchone()
            if old is not None and old[0] != payload:
                raise ValidationError("cohort ID already binds different content")
            self.db.execute(
                "INSERT OR IGNORE INTO cohorts VALUES(?,?,?)", (cohort_id, digest, payload)
            )
        return result

    def get(self, cohort_id):
        name(cohort_id)
        row = self.db.execute(
            "SELECT payload,fingerprint FROM cohorts WHERE id=?", (cohort_id,)
        ).fetchone()
        if row is None:
            raise ValidationError("unknown cohort")
        return decode(cohort_id, row[0], row[1])
