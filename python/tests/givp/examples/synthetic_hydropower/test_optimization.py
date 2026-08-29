"""Unit tests for the shared cross-language optimisation adapter."""

from __future__ import annotations

import numpy as np
import pandas as pd

from givp.examples.synthetic_hydropower.interop import canonical_cascade_config
from givp.examples.synthetic_hydropower.optimization import (
    evaluate_power_vector,
    load_optimization_definition,
    make_optimization_request,
    project_power_vector,
    summarize_result,
)
from givp.examples.synthetic_hydropower.paths import project_root


def _definition():  # type: ignore[no-untyped-def]
    return load_optimization_definition(
        project_root() / "interop" / "v1" / "optimization_definition.json"
    )


def test_projection_uses_the_nearest_valid_operating_power() -> None:
    """Map raw controls to off, minimum, and valid continuous powers."""
    definition = _definition()
    raw = np.zeros(48)
    raw[0:4] = [0.0, 22.49, 22.5, 80.0]
    raw[24:28] = [0.0, 15.99, 16.0, 70.0]

    schedule = project_power_vector(raw, definition)

    assert schedule.shape == (2, 24)
    assert schedule[0, :4].tolist() == [0.0, 0.0, 45.0, 80.0]
    assert schedule[1, :4].tolist() == [0.0, 0.0, 32.0, 70.0]


def test_request_uses_a_then_b_hourly_decision_order() -> None:
    """Keep the protocol schedule aligned with the documented 48-vector order."""
    definition = _definition()
    raw = np.arange(48, dtype=float)

    request = make_optimization_request(raw, definition, case_id="ordered")
    schedule = request["requests"][0]["target_power_mw"]  # type: ignore[index]

    assert schedule[0][0] == 0.0  # type: ignore[index]
    assert schedule[0][23] == 45.0  # type: ignore[index]
    assert schedule[1][0] == 32.0  # type: ignore[index]
    assert schedule[1][23] == 47.0  # type: ignore[index]


def test_evaluation_and_summary_use_the_canonical_physical_objective() -> None:
    """Expose the same finite objective and diagnostics returned by the worker."""
    definition = _definition()

    objective, result = evaluate_power_vector(np.zeros(48), definition)
    summary = summarize_result(result)

    assert objective == summary["objective"]
    assert np.isfinite(summary["energy_mwh"])
    assert np.isfinite(summary["power_deficit_mwh"])


def test_definition_is_anchored_to_the_frozen_typical_case_and_config() -> None:
    """Prevent independently maintained native metadata from drifting physically."""
    definition = _definition()
    cascade = canonical_cascade_config()
    inflows = pd.read_csv(
        project_root() / "benchmarks" / "v1.0.0" / "inputs" / "inflows.csv"
    )

    assert definition.scenario == "typical"
    assert definition.seed == 44
    assert np.allclose(
        definition.minimum_power_mw, [plant.min_power_mw for plant in cascade.plants]
    )
    assert np.allclose(
        definition.maximum_power_mw, [plant.max_power_mw for plant in cascade.plants]
    )
    assert np.allclose(
        definition.incremental_inflow_m3s,
        [
            inflows[(inflows["scenario"] == "typical") & (inflows["plant"] == plant)]
            .sort_values("period")["incremental_inflow_m3s"]
            .to_numpy()
            for plant in ("A", "B")
        ],
    )
