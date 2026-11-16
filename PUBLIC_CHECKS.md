# Public business incidents

The analyst froze two small cohorts and received misleading cumulative reports.

* overlap: support [1,2,3]; observation left covers (-infinity,2], count 4,
  and right covers [2,infinity), count 4. Every likelihood maximizer puts
  mass 1 at support 2. Expected cumulative ranges at [1,2,3] are
  [[0,0],[1,1],[1,1]]. The current checkout reports
  [[0.25,0.25],[0.75,0.75],[1,1]].
* unresolved: support [1,2,3]; one observation covers [1,2], count 4.
  Expected cumulative ranges at [1,2,3] are [[0,1],[1,1],[1,1]].
  The current checkout reports [[0.5,0.5],[1,1],[1,1]].

Run `python3.11 -B accident.py` to call the real public Study API for both.
It prints expected and actual endpoints, the fitted mass, and a marker.
It exits 1 with CENSOR_RANGE_COLLAPSED when either business expectation fails;
it exits 0 with CENSOR_RANGE_RESTORED only when both pass. Exceptions are
allowed to propagate and are not translated into a business-failure marker.

Both results must be correct together; fixing the unique-overlap example does
not justify collapsing the unresolved interval. Changing supported coordinates
or splitting identical interval counts must not change these probabilities.
Revisions imported after freezing must leave old fits and reports bound to
their existing frozen cohort, including after archive reopening.

The original suite includes these analysis boundaries, irrational interior
optima, partially identified distributions, numerical-budget failure and
independent exact certificates. Keep all original assertions and add any new
cases in separate files. After repair, run the full suite, accident.py and
the existing real demo. Report actual commands and outcomes, including any
environment checks that could not be executed.
