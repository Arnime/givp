# Python test layout

The test suite mirrors the responsibility of the code under test:

```text
tests/
  benchmark/  internal benchmark tools, quality gates, and performance
  fuzz/       fuzzing harness and decoder
  givp/       published package, including distributed examples
  fixtures/   data and objective functions shared across test groups
  conftest.py shared pytest fixtures
```

The default suite and the 95% coverage gate contain unit tests only. An
unmarked test is therefore part of the unit suite. Every non-unit suite has an
explicit marker and is excluded from the default marker expression: integration,
property-based, frozen benchmark regression, slow command, statistical quality,
and performance tests.

```powershell
poetry run pytest
```

Run each opt-in group explicitly:

```powershell
poetry run pytest -m integration tests --no-cov --override-ini="addopts="
poetry run pytest -m property tests/givp/test_properties.py --no-cov --override-ini="addopts=" -p no:randomly
poetry run pytest -m benchmark_regression tests --no-cov --override-ini="addopts="
poetry run pytest -m slow tests/benchmark --no-cov --override-ini="addopts="
poetry run pytest -m quality_gate tests/benchmark/test_quality.py --no-cov --override-ini="addopts="
poetry run pytest -m performance tests/benchmark/test_performance.py --benchmark-only --no-cov --override-ini="addopts="
```

Coverage must not be combined across suites. Property, integration, benchmark,
quality, and performance executions validate different concerns but do not help
the unit suite satisfy the 95% threshold.
