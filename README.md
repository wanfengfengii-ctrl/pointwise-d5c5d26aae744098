# Censoring Study

Python 3.11 standard-library library and CLI for finite-support, interval-censored
observations. Analysts import revisions, freeze explicitly selected observations,
fit a distribution, and publish cumulative probability ranges. SQLite archives
retain accepted revision history, immutable cohorts, successful fits and reports.
This checkout has the two business incidents documented in PUBLIC_CHECKS.md.

Run from the project directory:

```sh
python3.11 -B -m unittest discover -s tests -v
python3.11 -B accident.py
python3.11 -B -m censoring demo
python3.11 -B -m censoring run samples/workflow.json
```

The workflow runs in memory by default. To retain and reopen its archive, supply
`--db study.sqlite`. Replaying the sample on a fresh archive or in memory shows
the old report staying at 0.25 while a newly frozen cohort reports 0.75.
Individual API calls commit atomically; a workflow is a sequence of calls, not
one transaction. Errors print a JSON `error` and exit 2; success exits 0.
Setup installs nothing. The runtime manifest uses the original full-suite verify
and real demo argument arrays (version 1, kind cli, empty setup). Keep it usable.
After repair the full original suite and accident.py must pass; demo must show
actual analysis results. Keep all original test bytes unchanged; add separate
regressions and a short root-cause, handoff-invariant and actual-validation note.

## Python API

```python
from censoring import Observation, Study

with Study() as study:  # or Study("study.sqlite")
    study.import_observations([
        Observation("early", 1, 1, 2, 4),
        Observation("late", 1, 3, 3, 2),
    ])
    study.freeze("analysis-1", [1, 2, 3], ["early", "late"])
    result = study.fit("analysis-1")
    report = study.survival("analysis-1", [1, 2, 3], report_id="publication-1")
    print(report.ranges)
```

`survival` is the historical API name: each range is for
**P(T <= cutoff)**, not P(T > cutoff). Results use immutable dataclasses and
Decimal probabilities. A representative mass vector in a fit is one maximizer;
the report bounds cover every maximizing distribution. For the example, the
ranges are [0, 2/3], [2/3, 2/3], [1, 1]. They are identifiability ranges, not
confidence intervals. Float conversion of each endpoint has absolute error at
most 1e-8 within the supported domain.

## Observations and revisions

`Observation(id, rev, lower, upper, count)` describes a closed interval. None
means an unbounded endpoint; equal finite endpoints describe an exact event.
None on the left gives left censoring, None on the right gives right censoring.
The interval contributes its covered **total mass**, with integer multiplicity
`count`. There is no midpoint imputation or assumption that covered points are
independent observations.

IDs are nonempty valid Unicode strings of at most 120 characters. Revisions are
positive Python integers. Counts are integers in 1..20; bool is rejected.
Support values and finite endpoints are finite int/float inputs, normalized to
Python float. Comparisons use those normalized values. Lower must not exceed
upper. `Observation("early", 2, withdrawn=True)` withdraws an observation and
must carry no bounds or count.

`import_observations(iterable)` validates the whole batch, requires distinct IDs,
then applies it atomically. A lower revision is ignored, an equal current
revision with identical normalized content is replayed, and conflicting content
at that revision rejects the entire batch. Accepted higher revisions are retained
in `revisions(id)`; ignored revisions do not enter history. Receipts describe
the current revision for each requested ID in input order. `current(id)`
returns an immutable current record. Withdrawal does not delete prior snapshots.

## Frozen analysis and publication

`freeze(cohort_id, support, observation_ids)` requires 1..6 strictly increasing
support points and a nonempty explicit set of distinct, currently active IDs.
Every interval must cover at least one support point. Records with the same
covered indices are aggregated: at most 12 distinct patterns, each with summed
count at most 20. Thus an interval with count 4 may be split into counts 1 and 3.
Selection order does not change a cohort. Its content fingerprint binds support,
IDs, revisions, intervals and counts. Reusing a cohort ID requires exactly the
same normalized snapshot; otherwise it rejects. `cohort(id)` loads that snapshot.
Unknown/withdrawn selections or invalid support leave no half cohort.

`fit(cohort_id, max_iterations=100)` maximizes
sum(count * log(sum(covered mass))) over nonnegative masses summing to one.
Preserve the numerical publication criteria and 80-digit Decimal arithmetic.
For coverage A, fitted pattern probabilities q and counts w, the mass gradient
is g_j=sum_i(w_i*A_ij/q_i). Every g_j is at most N + N*1e-26, and
positive-mass coordinates satisfy abs(g_j-N)<=N*1e-26, where N is total count.
A numerically solved interior has stationarity tolerance N*1e-32.
No certificate means FitError, never a success with partial numerical values.
`max_iterations` is an integer in 0..300 controlling each candidate's numerical iteration budget.
Zero allows already stationary faces, but fails on a nonstationary 1:3 exact
two-point cohort; the regression uses this actual numerical failure.
A failed attempt keeps any previously published fit unchanged.
`fit_result(id)` loads a successful fit or raises FitError.

Positive pattern counts make the maximizing pattern-probability vector unique.
FitResult retains cohort_id, fingerprint, representative mass, pattern_probabilities
in cohort pattern order and log_likelihood; Decimal values retain full precision
through saving and loading. All maximizing masses must preserve the fitted
coverage probabilities, nonnegativity and total mass one. Coverage rank decisions
are exact; feasible-set checks use absolute 1e-22 Decimal tolerance. Identical
coverage columns may exchange mass, and zero-mass faces remain legal.
Equivalent numerical formulations, full recomputation and finite enumeration
are allowed. Do not add external dependencies or change the likelihood by
pseudocounts or arbitrary identifying anchors.

`survival(cohort_id, cutoffs, report_id=...)` requires a published fit and a
nonempty list of support-valued cutoffs. It preserves request order and repeated
cutoffs. It saves one immutable report only after all endpoints succeed.
`report(report_id)` reads it later. Reusing a report ID requires the same cohort,
fingerprint, ordered cutoffs and computed result. Any conflict rejects without
overwriting it. Fits and reports always read frozen content, never current
observations. Additional cutoffs and refitting an old cohort keep that binding.

ValidationError covers invalid business input, unknown IDs, and immutable-ID
conflicts. FitError covers absent successful fits or unsatisfied numerical
publication criteria. SQLite or filesystem failures propagate from the Python
API. A Study owns one connection and is intended for one worker; distributed
coordination, concurrent writers, automatic support selection, continuous-time
estimation, significance testing and regression models are outside this API.
Use context management or close() to release the connection.

## Modules and regression

- `observations.py`: current revisions, atomic import and accepted history.
- `cohorts.py`: support validation, pattern aggregation and frozen content.
- `fitting.py` / `numerics.py`: likelihood, numerical publication and mass geometry.
- `reporting.py`: cumulative extrema and immutable report publication.
- `study.py`: the SQLite archive and public facade.
- `cli.py`: JSON workflows and an end-to-end report demonstration.

Tests cover exact 1:3 counts, fully ambiguous intervals, overlapping left/right
censoring, strict zero mass, partially identified mass, an irrational interior
solution, duplicate-pattern splitting, order-preserving support relabeling,
revisions, withdrawals, rollback, invalid freezes, numerical failure and saved
report identity. Independent Fraction certificates verify rational KKT conditions
and solve full-coordinate active-zero equations for endpoint expectations.
Fixed-seed partition fixtures have exact optimal probabilities by construction.
Disk tests use only TemporaryDirectory and check close/reopen, fixed historical
results, archive version and foreign keys. The sample workflow is finite and
uses the public API through the CLI.

## JSON workflow and repair scope

The workflow input is an array of objects with op: import uses observations
(Observation fields); freeze uses cohort/support/ids; fit uses cohort and optional
max_iterations; survival uses cohort/cutoffs/report; read_report uses report;
current uses id. Output is an array of {"op": operation, "result": value};
dataclasses become objects, tuples become arrays and Decimal values become
strings. samples/workflow.json is the complete correction example.

Repair the existing distribution fit and cumulative-range report together,
with the original interfaces, publication rules and frozen bindings. There is
no requirement for new analysis features, performance optimization or concurrent
workers. tests/oracle.py is an independent rational small-example certificate
helper; it requires a supplied optimal mass and is not a likelihood optimizer.
