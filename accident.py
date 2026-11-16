"""Observable regression for the two public censored-data incidents."""
import json
from censoring import Observation, Study


CASES = (
    ("overlap", [1, 2, 3], [(None, 2, 4), (2, None, 4)],
     [(0, 0), (1, 1), (1, 1)]),
    ("unresolved", [1, 2, 3], [(1, 2, 4)],
     [(0, 1), (1, 1), (1, 1)]),
)


def run():
    evidence = []
    failed = False
    for label, support, rows, expected in CASES:
        with Study() as study:
            records = [Observation(str(i), 1, *row) for i, row in enumerate(rows)]
            study.import_observations(records)
            study.freeze(label, support, [r.id for r in records])
            fitted = study.fit(label)
            report = study.survival(label, support, report_id=label + "-report")
            actual = [(float(r.lower), float(r.upper)) for r in report.ranges]
            matches = all(abs(a - e) <= 1e-8
                          for pair, want in zip(actual, expected)
                          for a, e in zip(pair, want))
            failed = failed or not matches
            evidence.append({"case": label, "mass": [str(p) for p in fitted.mass],
                             "expected": expected, "actual": actual, "matches": matches})
    print(json.dumps({"checks": evidence,
                      "marker": "CENSOR_RANGE_COLLAPSED" if failed else "CENSOR_RANGE_RESTORED"},
                     sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
