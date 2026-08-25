"""Facade for deterministic hydropower benchmark execution and persistence."""

from givp.examples.synthetic_hydropower.benchmark.deterministic.execution import (
    DeterministicRun,
    load_frozen_inflows,
    run_deterministic_benchmark,
)
from givp.examples.synthetic_hydropower.benchmark.deterministic.persistence import (
    save_deterministic_benchmark,
)

__all__ = [
    "DeterministicRun",
    "load_frozen_inflows",
    "run_deterministic_benchmark",
    "save_deterministic_benchmark",
]
