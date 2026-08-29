"""Run the Python GIVP against the synthetic hydropower objective."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path

import numpy as np
from adapter import HydropowerWorker
from givp import GIVPConfig, givp
from givp.examples.synthetic_hydropower.optimization import (
    load_optimization_definition,
    summarize_result,
)


def main(definition_path: Path) -> None:
    """Optimise the frozen scenario and print a language-neutral JSON summary."""
    definition = load_optimization_definition(definition_path)
    settings = definition.optimizer
    config = GIVPConfig(
        direction="minimize",
        max_iterations=_int_setting(settings, "max_iterations"),
        vnd_iterations=_int_setting(settings, "vnd_iterations"),
        ils_iterations=_int_setting(settings, "ils_iterations"),
        num_candidates_per_step=_int_setting(settings, "num_candidates_per_step"),
        use_elite_pool=_bool_setting(settings, "use_elite_pool"),
        use_convergence_monitor=_bool_setting(settings, "use_convergence_monitor"),
        n_workers=_int_setting(settings, "n_workers"),
    )
    worker = HydropowerWorker()
    try:
        baseline = worker.evaluate(np.zeros(48), definition, case_id="baseline")
        baseline_summary = summarize_result(baseline)
        baseline_objective = baseline_summary["objective"]

        def objective(vector: np.ndarray) -> float:
            result = worker.evaluate(vector, definition, case_id="candidate")
            return summarize_result(result)["objective"]

        result = givp(
            objective,
            bounds=definition.bounds,
            config=config,
            seed=definition.seed,
        )
        physical = worker.evaluate(np.asarray(result.x), definition, case_id="optimized")
        physical_summary = summarize_result(physical)
        objective_value = physical_summary["objective"]
    finally:
        worker.close()
    print(
        json.dumps(
            {
                "language": "python",
                "scenario": definition.scenario,
                "baseline_objective": baseline_objective,
                "optimizer_objective": result.fun,
                "objective": objective_value,
                "energy_mwh": physical_summary["energy_mwh"],
                "level_penalty": physical_summary["level_penalty"],
                "baseline": baseline_summary,
                "summary": physical_summary,
                "target_power_mw": _power_schedule(physical),
            },
            allow_nan=False,
        )
    )


def _int_setting(settings: Mapping[str, object], name: str) -> int:
    """Return one validated positive integer from the frozen definition."""
    value = settings.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"optimizer setting {name!r} must be an integer")
    return value


def _bool_setting(settings: Mapping[str, object], name: str) -> bool:
    """Return one validated Boolean from the frozen definition."""
    value = settings.get(name)
    if not isinstance(value, bool):
        raise TypeError(f"optimizer setting {name!r} must be a Boolean")
    return value


def _power_schedule(result: Mapping[str, object]) -> object:
    """Return the protocol power schedule after validating its container."""
    power = result.get("power")
    if not isinstance(power, Mapping) or "target_power_mw" not in power:
        raise ValueError("physical result has no target_power_mw")
    return power["target_power_mw"]


if __name__ == "__main__":
    main(Path(sys.argv[1]))
