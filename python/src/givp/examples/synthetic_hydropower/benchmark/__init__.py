"""Facade for synthetic hydropower benchmark artifact management."""

from givp.examples.synthetic_hydropower.benchmark.artifacts import BenchmarkArtifacts
from givp.examples.synthetic_hydropower.benchmark.promotion import (
    promote_benchmark_version,
)
from givp.examples.synthetic_hydropower.benchmark.results import (
    save_benchmark_results,
)

__all__ = [
    "BenchmarkArtifacts",
    "promote_benchmark_version",
    "save_benchmark_results",
]
