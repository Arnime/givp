"""Facade for synthetic hydropower benchmark artifact management."""

from givp.examples.synthetic_hydropower.benchmark.artifacts import BenchmarkArtifacts
from givp.examples.synthetic_hydropower.benchmark.definition import (
    DeterministicDefinition,
    load_deterministic_definition,
)
from givp.examples.synthetic_hydropower.benchmark.deterministic import (
    DeterministicRun,
    load_frozen_inflows,
    run_deterministic_benchmark,
    save_deterministic_benchmark,
)
from givp.examples.synthetic_hydropower.benchmark.promotion import (
    promote_benchmark_version,
)
from givp.examples.synthetic_hydropower.benchmark.results import (
    save_benchmark_results,
)

__all__ = [
    "BenchmarkArtifacts",
    "DeterministicDefinition",
    "DeterministicRun",
    "load_deterministic_definition",
    "load_frozen_inflows",
    "promote_benchmark_version",
    "run_deterministic_benchmark",
    "save_benchmark_results",
    "save_deterministic_benchmark",
]
