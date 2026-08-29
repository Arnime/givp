"""Facade for deterministic hydropower benchmark execution and persistence."""

from givp.examples.synthetic_hydropower.benchmark.deterministic.execution import (
    DeterministicRun,
    load_frozen_inflows,
    run_deterministic_benchmark,
)
from givp.examples.synthetic_hydropower.benchmark.deterministic.interop import (
    build_batch_request,
    compare_interop_artifacts,
    run_from_worker_response,
    write_interop_artifacts,
)
from givp.examples.synthetic_hydropower.benchmark.deterministic.persistence import (
    save_deterministic_benchmark,
)

__all__ = [
    "DeterministicRun",
    "build_batch_request",
    "compare_interop_artifacts",
    "load_frozen_inflows",
    "run_deterministic_benchmark",
    "run_from_worker_response",
    "save_deterministic_benchmark",
    "write_interop_artifacts",
]
