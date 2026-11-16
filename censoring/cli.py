"""JSON workflows over the same public API used by Python clients."""
import argparse
from dataclasses import asdict, is_dataclass
from decimal import Decimal
import json
import sqlite3
from . import Observation, Study, FitError, ValidationError


def serial(value):
    if is_dataclass(value):
        return serial(asdict(value))
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: serial(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(item) for item in value]
    return value


def execute(study, operations):
    results = []
    for event in operations:
        operation = event["op"]
        if operation == "import":
            records = [Observation(**record) for record in event["observations"]]
            value = study.import_observations(records)
        elif operation == "freeze":
            value = study.freeze(event["cohort"], event["support"], event["ids"])
        elif operation == "fit":
            value = study.fit(event["cohort"], max_iterations=event.get("max_iterations", 100))
        elif operation == "survival":
            value = study.survival(event["cohort"], event["cutoffs"], report_id=event["report"])
        elif operation == "read_report":
            value = study.report(event["report"])
        elif operation == "current":
            value = study.current(event["id"])
        else:
            raise ValidationError("unknown workflow operation")
        results.append({"op": operation, "result": serial(value)})
    return results


def demonstration():
    with Study() as study:
        study.import_observations([
            Observation("a", 1, 1, 1, 1), Observation("b", 1, 2, 2, 3)
        ])
        study.freeze("original", [1, 2], ["a", "b"])
        study.fit("original")
        old = study.survival("original", [1, 2], report_id="original-report")
        study.import_observations([
            Observation("a", 2, 1, 1, 3), Observation("b", 2, 2, 2, 1)
        ])
        study.freeze("corrected", [1, 2], ["a", "b"])
        study.fit("corrected")
        new = study.survival("corrected", [1, 2], report_id="corrected-report")
        study.import_observations([Observation("interval", 1, 1, 2, 4)])
        study.freeze("unresolved", [1, 2, 3], ["interval"])
        study.fit("unresolved")
        ambiguous = study.survival("unresolved", [1, 2, 3], report_id="range-report")
        study.import_observations([
            Observation("left", 1, None, 2, 4), Observation("right", 1, 2, None, 4)
        ])
        study.freeze("overlap", [1, 2, 3], ["left", "right"])
        study.fit("overlap")
        overlap = study.survival("overlap", [1, 2, 3], report_id="overlap-report")
        assert study.report("original-report") == old
        assert abs(float(old.ranges[0].lower) - .25) < 1e-8
        assert abs(float(new.ranges[0].upper) - .75) < 1e-8
        assert ambiguous.ranges[0].lower == 0 and ambiguous.ranges[0].upper == 1
        assert overlap.ranges[0].upper == 0 and overlap.ranges[1].lower == 1
        return {"original": serial(old), "corrected": serial(new),
                "unresolved": serial(ambiguous), "overlap": serial(overlap),
                "old_report_after_correction": serial(study.report("original-report"))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo")
    run = sub.add_parser("run")
    run.add_argument("workflow")
    run.add_argument("--db", default=":memory:")
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            result = demonstration()
        else:
            with open(args.workflow, encoding="utf-8") as stream:
                operations = json.load(stream)
            with Study(args.db) as study:
                result = execute(study, operations)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
        return 0
    except (ValidationError, FitError, KeyError, TypeError, ValueError,
            OSError, sqlite3.Error) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 2
