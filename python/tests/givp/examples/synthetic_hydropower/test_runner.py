"""Tests for standalone hydropower configuration and optimization."""

import json
from pathlib import Path

import numpy as np

from givp.examples.synthetic_hydropower.runner import (
    load_experiment_config,
    optimize_scenario,
)


def test_optimization_returns_a_finite_fictional_solution(tmp_path: Path) -> None:
    payload = {
        "plants": [
            {"name": "A", "initial_volume_hm3": 1.0, "min_volume_hm3": 0.5, "max_volume_hm3": 1.5, "maximorum_volume_hm3": 1.7, "min_level_m": 100.0, "max_level_m": 110.0, "head_m": 50.0, "efficiency": 0.9, "min_power_mw": 1.0, "max_power_mw": 5.0, "upstream_level_coefficients": [0.0, 1.1, -0.1, 0.0, 0.0], "downstream_base_level_m": 55.0, "downstream_level_range_m": 4.0, "downstream_level_coefficients": [0.0, 0.8, 0.2, 0.0, 0.0], "sanitary_spill_flow_m3s": 0.5, "spill_response": 0.6, "spill_response_exponent": 1.3, "maximorum_level_m": 112.0},
            {"name": "B", "initial_volume_hm3": 1.0, "min_volume_hm3": 0.5, "max_volume_hm3": 1.5, "maximorum_volume_hm3": 1.7, "min_level_m": 80.0, "max_level_m": 90.0, "head_m": 40.0, "efficiency": 0.9, "min_power_mw": 1.0, "max_power_mw": 5.0, "upstream_level_coefficients": [0.0, 0.9, 0.1, 0.0, 0.0], "downstream_base_level_m": 45.0, "downstream_level_range_m": 4.0, "downstream_level_coefficients": [0.0, 0.8, 0.2, 0.0, 0.0], "sanitary_spill_flow_m3s": 0.25, "spill_response": 0.6, "spill_response_exponent": 1.3, "maximorum_level_m": 92.0}
        ]
    }
    definition = {
        "cascade": {
            "periods": 2,
            "period_hours": 1.0,
            "travel_time_steps": 1,
            "level_penalty_weight": 1000.0,
        },
        "optimizer": {"max_iterations": 2, "vnd_iterations": 2, "ils_iterations": 1},
        "scenarios": [
            {"name": "typical", "upstream_base": 100.0, "downstream_base": 20.0, "variability": 0.0, "profile": "stable", "seed": 1}
        ],
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    definition_path = tmp_path / "definition.json"
    definition_path.write_text(json.dumps(definition), encoding="utf-8")
    result = optimize_scenario(
        load_experiment_config(config_path, definition_path), "typical", seed=1
    )
    assert np.isfinite(result.objective)
    assert result.energy_mwh > 0.0
