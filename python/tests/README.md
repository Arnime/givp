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

The default suite excludes slow commands, statistical quality gates, and
performance measurements:

```powershell
poetry run pytest
```

Run each opt-in group explicitly:

```powershell
poetry run pytest -m slow tests/benchmark
poetry run pytest -m quality_gate tests/benchmark/test_quality.py
poetry run pytest -m performance tests/benchmark/test_performance.py --benchmark-only
```
