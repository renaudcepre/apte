"""Adults suite - parent of workers and unemployed.

Demonstrates 3-level suite hierarchy: session → adults → workers/unemployed.
"""

from apte import ApteSuite
from examples.yorkshire.tests.suites.adults.unemployed.suite import unemployed_suite
from examples.yorkshire.tests.suites.adults.workers import workers_suite

adults_suite = ApteSuite("Adults")
adults_suite.add_suite(workers_suite)
adults_suite.add_suite(unemployed_suite)

__all__ = ["adults_suite"]
