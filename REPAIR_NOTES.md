# Repair notes: interval-censored fit and cumulative ranges

## Root cause

Two defects in the existing fit/report chain produced the incidents in
PUBLIC_CHECKS.md:

1. `numerics.maximize` never maximized the likelihood. It imputed each
   observation's count uniformly over its covered support points (the
   midpoint-style allocation the README forbids) and published the
   normalized vector. Overlapping left/right-censored intervals were
   therefore reported as mass 0.25/0.5/0.25 instead of the unique
   maximizer 0/1/0, and one unresolved [1,2] interval was frozen at a
   0.5/0.5 split.
2. `reporting.survival` evaluated cumulative probabilities only at the
   single stored representative mass, so any partially identified
   cohort collapsed to a point value instead of the min/max over all
   maximizing distributions.

## Fix (interfaces, publication rules and frozen bindings unchanged)

- `censoring/numerics.py` — `maximize` now truly maximizes
  `sum(count * log(covered mass))` over nonnegative masses summing to 1:
  - enumerates the simplex faces (support <= 6, so at most 63), keeping
    faces whose coverage-plus-sum system has exact full column rank
    (Fraction rank via `independent_rows`);
  - solves each face's interior stationarity system `g_j = N` with a
    safeguarded Newton iteration (positivity line search, EM
    multiplicative fallback) in 80-digit Decimal arithmetic;
    `max_iterations` remains the per-face budget — 0 still certifies
    already stationary faces and still fails on the nonstationary 1:3
    exact two-point cohort;
  - publishes the first face satisfying the global KKT bounds
    (`g_j <= N + N*1e-26`, positive-mass `|g_j - N| <= N*1e-26`,
    interior stationarity `N*1e-32`); coordinates outside the face are
    exactly zero, so zero-mass faces and identical-column mass exchange
    stay legal. No certificate still means FitError and a failed fit
    publishes nothing.
- `censoring/reporting.py` — `survival` now reports, for every cutoff,
  the minimum and maximum of P(T <= cutoff) over **every** maximizing
  distribution: `numerics.mass_vertices` enumerates the basic feasible
  solutions of `{p >= 0, sum p = 1, A p = fitted probabilities}` (exact
  rank, 1e-22 absolute feasibility tolerance) from the published fit
  bound to the frozen cohort. Reports are still saved only after all
  endpoints succeed, and report-ID conflicts still reject without
  overwriting.

## Handoff invariants

- Fits and reports read frozen cohort content only; revisions imported
  after freezing never change published fits or reports, including
  across archive close/reopen (verified below and by
  `tests/test_repair.py::test_correction_keeps_old_fit_and_report_after_reopen`).
- 80-digit Decimal arithmetic, gradient certificate tolerances,
  FitError/ValidationError split, atomic publication, and all original
  business assertions are preserved; no new dependencies (standard
  library only); all original test files are byte-unchanged.

## Actual validation (commands run, from the project directory)

- `python3.11 -B -m unittest discover -s tests -v` — OK, 38 tests
  (31 original + 7 new regressions in `tests/test_repair.py`).
- `python3.11 -B accident.py` — prints `CENSOR_RANGE_RESTORED`,
  exit 0; overlap now [[0,0],[1,1],[1,1]] with mass (0,1,0),
  unresolved now [[0,1],[1,1],[1,1]].
- `python3.11 -B -m censoring demo` — exit 0; old report stays 0.25,
  corrected cohort reports 0.75, unresolved range [0,1], overlap
  [0,0]/[1,1].
- `python3.11 -B -m censoring run samples/workflow.json` — exit 0;
  baseline report stays 0.25 while the corrected cohort reports 0.75.
- `--db` archive flow: fresh-archive run exits 0; after close/reopen
  the old fit and report are byte-identical and a corrected cohort
  reports 0.75. (Replaying the same workflow twice into one archive
  rejects with "cohort ID already binds different content" — the
  documented immutable-ID rule; replay is defined for a fresh archive
  or in memory.)
- Independent check: the repaired fit and range enumeration were also
  verified against `tests/oracle.py` rational certificates on all 6
  hand examples and all 24 fixed-seed partition fixtures (covered by
  the suite), plus the new incident regressions.
