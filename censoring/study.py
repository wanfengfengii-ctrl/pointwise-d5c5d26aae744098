"""Single-worker SQLite archive for revisions, cohorts, fits and reports."""
import sqlite3
from .cohorts import Cohorts
from .errors import ValidationError
from .fitting import Fitting
from .observations import Observations
from .reporting import Reporting


class Study:
    """Own one archive connection. Calls are atomic; instances are not shared across threads."""
    def __init__(self, path=":memory:"):
        self._db = sqlite3.connect(path)
        try:
            self._db.execute("PRAGMA foreign_keys=ON")
            version = self._db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ValidationError("unsupported archive version")
            if version == 0:
                if self._db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchone():
                    raise ValidationError("unrecognized archive")
                with self._db:
                    self._db.execute("BEGIN")
                    for statement in (
                        "CREATE TABLE observations(id TEXT PRIMARY KEY,rev TEXT NOT NULL,"
                        "payload TEXT NOT NULL)",
                        "CREATE TABLE history(id TEXT NOT NULL,rev TEXT NOT NULL,"
                        "payload TEXT NOT NULL,PRIMARY KEY(id,rev))",
                        "CREATE TABLE cohorts(id TEXT PRIMARY KEY,fingerprint TEXT NOT NULL,"
                        "payload TEXT NOT NULL)",
                        "CREATE TABLE fits(cohort_id TEXT PRIMARY KEY REFERENCES cohorts(id),"
                        "fingerprint TEXT NOT NULL,payload TEXT NOT NULL)",
                        "CREATE TABLE reports(id TEXT PRIMARY KEY,cohort_id TEXT NOT NULL "
                        "REFERENCES fits(cohort_id),fingerprint TEXT NOT NULL,payload TEXT NOT NULL)",
                        "PRAGMA user_version=1",
                    ):
                        self._db.execute(statement)
            self._observations = Observations(self._db)
            self._cohorts = Cohorts(self._db, self._observations)
            self._fitting = Fitting(self._db, self._cohorts)
            self._reporting = Reporting(self._db, self._cohorts, self._fitting)
        except BaseException:
            self._db.close()
            raise

    def import_observations(self, records):
        return self._observations.import_observations(records)

    def current(self, observation_id):
        return self._observations.current(observation_id)

    def revisions(self, observation_id):
        return self._observations.revisions(observation_id)

    def freeze(self, cohort_id, support, observation_ids):
        return self._cohorts.freeze(cohort_id, support, observation_ids)

    def cohort(self, cohort_id):
        return self._cohorts.get(cohort_id)

    def fit(self, cohort_id, *, max_iterations=100):
        return self._fitting.fit(cohort_id, max_iterations=max_iterations)

    def fit_result(self, cohort_id):
        return self._fitting.get(cohort_id)

    def survival(self, cohort_id, cutoffs, *, report_id):
        return self._reporting.survival(cohort_id, cutoffs, report_id=report_id)

    def report(self, report_id):
        return self._reporting.get(report_id)

    def close(self):
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *exception):
        self.close()
