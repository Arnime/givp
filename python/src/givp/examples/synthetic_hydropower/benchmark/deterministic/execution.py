"""Execution and frozen-input loading for the deterministic balance protocol."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from givp.examples.synthetic_hydropower.benchmark.cases import (
    PowerCase,
    build_power_cases,
)
from givp.examples.synthetic_hydropower.benchmark.definition import (
    DeterministicDefinition,
)
from givp.examples.synthetic_hydropower.model import (
    PowerScheduleResult,
    simulate_power_schedule,
)
from givp.examples.synthetic_hydropower.scenarios import generate_inflows


@dataclass(frozen=True)
class DeterministicRun:
    """Frozen inputs, factorial schedules and computed physical results."""

    inflows: Mapping[str, NDArray[np.float64]]
    cases: Sequence[PowerCase]
    results: Mapping[str, PowerScheduleResult]


def run_deterministic_benchmark(
    definition: DeterministicDefinition,
    frozen_inflows: Mapping[str, NDArray[np.float64]] | None = None,
) -> DeterministicRun:
    """Execute all 252 cases without invoking GIVP."""
    inflows = (
        dict(frozen_inflows)
        if frozen_inflows is not None
        else {
            scenario.definition.name: generate_inflows(
                scenario.definition, definition.cascade.periods, scenario.seed
            )
            for scenario in definition.scenarios
        }
    )
    expected = {scenario.definition.name for scenario in definition.scenarios}
    if set(inflows) != expected:
        raise ValueError("frozen inflows must contain exactly the versioned scenarios")
    cases = tuple(
        case
        for scenario in definition.scenarios
        for case in build_power_cases(definition.cascade, scenario.definition.name)
    )
    results = {
        case.case_id: simulate_power_schedule(
            definition.cascade, inflows[case.scenario], case.target_power_mw
        )
        for case in cases
    }
    return DeterministicRun(inflows=inflows, cases=cases, results=results)


def load_frozen_inflows(
    path: Path, definition: DeterministicDefinition
) -> dict[str, NDArray[np.float64]]:
    """Load the canonical 336-row inflow table into simulation arrays."""
    frame = pd.read_csv(path)
    inflows: dict[str, NDArray[np.float64]] = {}
    for scenario in definition.scenarios:
        name = scenario.definition.name
        subset = frame.loc[frame["scenario"] == name]
        values = np.vstack(
            [
                subset.loc[subset["plant"] == plant]
                .sort_values("period")["incremental_inflow_m3s"]
                .to_numpy(dtype=np.float64)
                for plant in ("A", "B")
            ]
        )
        if values.shape != (2, definition.cascade.periods):
            raise ValueError(f"invalid frozen inflow shape for scenario {name!r}")
        inflows[name] = values
    return inflows
