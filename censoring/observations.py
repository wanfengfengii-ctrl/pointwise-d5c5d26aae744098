"""Atomic current revisions and an append-only accepted revision history."""
from dataclasses import asdict, dataclass
import json
import math
from .errors import ValidationError


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def name(value):
    if not isinstance(value, str) or not value or len(value) > 120:
        raise ValidationError("IDs must be nonempty strings of at most 120 characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValidationError("IDs must be valid Unicode") from None
    return value


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError("support and interval endpoints must be finite numbers")
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise ValidationError("number is outside the finite range") from None
    if not math.isfinite(result):
        raise ValidationError("number must be finite")
    return result


@dataclass(frozen=True)
class Observation:
    id: str
    rev: int
    lower: float | None = None
    upper: float | None = None
    count: int | None = None
    withdrawn: bool = False


@dataclass(frozen=True)
class Receipt:
    id: str
    rev: int
    withdrawn: bool


def validate(record):
    if not isinstance(record, Observation):
        raise ValidationError("expected Observation")
    name(record.id)
    if type(record.rev) is not int or record.rev < 1:
        raise ValidationError("revision must be a positive integer")
    if type(record.withdrawn) is not bool:
        raise ValidationError("withdrawn must be boolean")
    lo = None if record.lower is None else number(record.lower)
    hi = None if record.upper is None else number(record.upper)
    if record.withdrawn:
        if lo is not None or hi is not None or record.count is not None:
            raise ValidationError("withdrawal carries no interval or count")
    else:
        if type(record.count) is not int or not 1 <= record.count <= 20:
            raise ValidationError("count must be an integer in 1..20")
        if lo is not None and hi is not None and lo > hi:
            raise ValidationError("empty interval")
    return Observation(record.id, record.rev, lo, hi, record.count, record.withdrawn)


def unpack(text):
    return Observation(**json.loads(text))


class Observations:
    def __init__(self, connection):
        self.db = connection

    def import_observations(self, records):
        batch = tuple(validate(record) for record in records)
        if len({r.id for r in batch}) != len(batch):
            raise ValidationError("an ID may occur only once per batch")
        receipts = []
        with self.db:
            for record in batch:
                payload = encode(asdict(record))
                row = self.db.execute(
                    "SELECT rev,payload FROM observations WHERE id=?", (record.id,)
                ).fetchone()
                current_rev = int(row[0]) if row else None
                if row and current_rev == record.rev and row[1] != payload:
                    raise ValidationError("conflicting content at the current revision")
                if row is None or record.rev > current_rev:
                    self.db.execute(
                        "INSERT INTO history VALUES(?,?,?)",
                        (record.id, str(record.rev), payload),
                    )
                    self.db.execute(
                        "INSERT INTO observations VALUES(?,?,?) "
                        "ON CONFLICT(id) DO UPDATE SET rev=excluded.rev,payload=excluded.payload",
                        (record.id, str(record.rev), payload),
                    )
                    current = record
                else:
                    current = unpack(row[1])
                receipts.append(Receipt(current.id, current.rev, current.withdrawn))
        return tuple(receipts)

    def current(self, observation_id):
        name(observation_id)
        row = self.db.execute(
            "SELECT payload FROM observations WHERE id=?", (observation_id,)
        ).fetchone()
        if row is None:
            raise ValidationError("unknown observation")
        return unpack(row[0])

    def revisions(self, observation_id):
        self.current(observation_id)
        records = [unpack(row[0]) for row in self.db.execute(
            "SELECT payload FROM history WHERE id=?", (observation_id,)
        )]
        return tuple(sorted(records, key=lambda record: record.rev))
