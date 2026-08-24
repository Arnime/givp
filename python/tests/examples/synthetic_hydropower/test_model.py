"""Tests for the fictional cascade mass-balance model."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from givp.examples.synthetic_hydropower.model import (
    CascadeConfig,
    PlantConfig,
    simulate_cascade,
    simulate_power_schedule,
)
from givp.examples.synthetic_hydropower.model.curves import upstream_level
from givp.examples.synthetic_hydropower.model.dispatch import level_control_spill
from givp.examples.synthetic_hydropower.paths import (
    default_config_path,
    default_output_dir,
)
from givp.examples.synthetic_hydropower.scenarios import (
    ScenarioDefinition,
    generate_inflows,
)


@pytest.fixture
def config() -> CascadeConfig:
    plant_a = PlantConfig(
        name="A",
        initial_volume_hm3=1.0,
        min_volume_hm3=0.5,
        max_volume_hm3=1.5,
        maximorum_volume_hm3=1.7,
        min_level_m=100.0,
        max_level_m=110.0,
        head_m=50.0,
        efficiency=0.9,
        min_power_mw=1.0,
        max_power_mw=10.0,
        upstream_level_coefficients=(0.0, 1.4166667, -0.9166667, 0.5, 0.0),
        downstream_base_level_m=55.0,
        downstream_level_range_m=4.0,
        downstream_level_coefficients=(0.0, 0.8, 0.2, 0.0, 0.0),
        sanitary_spill_flow_m3s=0.5,
        spill_response=0.6,
        spill_response_exponent=1.3,
        maximorum_level_m=112.0,
    )
    plant_b = PlantConfig(
        name="B",
        initial_volume_hm3=1.0,
        min_volume_hm3=0.5,
        max_volume_hm3=1.5,
        maximorum_volume_hm3=1.7,
        min_level_m=80.0,
        max_level_m=90.0,
        head_m=40.0,
        efficiency=0.9,
        min_power_mw=1.0,
        max_power_mw=10.0,
        upstream_level_coefficients=(0.0, 1.4166667, -0.9166667, 0.5, 0.0),
        downstream_base_level_m=45.0,
        downstream_level_range_m=4.0,
        downstream_level_coefficients=(0.0, 0.8, 0.2, 0.0, 0.0),
        sanitary_spill_flow_m3s=0.25,
        spill_response=0.6,
        spill_response_exponent=1.3,
        maximorum_level_m=92.0,
    )
    return CascadeConfig((plant_a, plant_b), 3, 1.0, 1, 1000.0)


def test_scenarios_are_seeded_and_non_negative() -> None:
    scenario = ScenarioDefinition("typical", 100.0, 30.0, 0.1)
    first = generate_inflows(scenario, 24, 8)
    assert np.array_equal(first, generate_inflows(scenario, 24, 8))
    assert np.all(generate_inflows(scenario, 24, 9) >= 0.0)


def test_default_paths_do_not_depend_on_the_current_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    assert default_config_path().name == "base.json"
    assert default_output_dir().name == "output"


def test_upstream_defluence_arrives_after_one_period(config: CascadeConfig) -> None:
    requested = np.zeros((2, 3))
    requested[0, 0] = config.plants[0].min_flow_m3s
    result = simulate_cascade(config, np.zeros((2, 3)), requested)
    assert result.upstream_arrival_m3s[1, 0] == 0.0
    assert result.upstream_arrival_m3s[1, 1] == pytest.approx(
        result.defluent_flow_m3s[0, 0]
    )


def test_spill_and_level_penalty_are_reported(config: CascadeConfig) -> None:
    inflows = np.array([[1_000.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
    full_plant_a = replace(config.plants[0], initial_volume_hm3=1.5)
    full_config = CascadeConfig(
        (full_plant_a, config.plants[1]), 3, 1.0, 1, 1000.0
    )
    result = simulate_cascade(full_config, inflows, np.zeros((2, 3)))
    expected_capacity_spill = (
        full_plant_a.sanitary_spill_flow_m3s
        + inflows[0, 0]
        - full_plant_a.max_flow_m3s
    )
    assert result.spill_flow_m3s[0, 0] > expected_capacity_spill
    assert result.sanitary_spill_flow_m3s[0, 0] == pytest.approx(0.5)
    assert result.capacity_spill_flow_m3s[0, 0] == pytest.approx(
        inflows[0, 0] - full_plant_a.max_flow_m3s
    )
    assert result.level_control_spill_flow_m3s[0, 0] > 0.0
    assert result.defluent_flow_m3s[0, 0] == pytest.approx(result.spill_flow_m3s[0, 0])
    assert result.level_penalty > 0.0


def test_minimum_level_penalty_is_accumulated_for_each_plant_and_period(
    config: CascadeConfig,
) -> None:
    depleted_plant_a = replace(config.plants[0], initial_volume_hm3=0.5)
    depleted_config = CascadeConfig(
        (depleted_plant_a, config.plants[1]), 3, 1.0, 1, 1000.0
    )
    requested = np.full((2, 3), 1_000.0)

    result = simulate_cascade(depleted_config, np.zeros((2, 3)), requested)

    expected = 1000.0 * np.maximum(
        0.0, depleted_plant_a.min_level_m - result.level_m[0, 1:]
    ) ** 2
    assert np.allclose(result.minimum_level_penalty_by_period[0], expected)
    assert result.minimum_level_penalty > 0.0
    assert result.level_penalty == pytest.approx(
        result.minimum_level_penalty + result.maximum_level_penalty
    )


def test_unit_switch_penalty_discourages_shutdown_and_restart(
    config: CascadeConfig,
) -> None:
    switch_config = replace(config, unit_switch_penalty_weight=250.0)
    requested = np.zeros((2, 3))
    requested[0, 1] = switch_config.plants[0].min_flow_m3s

    result = simulate_cascade(switch_config, np.zeros((2, 3)), requested)

    assert result.unit_on[0].tolist() == [False, True, False]
    assert result.unit_switch_penalty_by_period[0].tolist() == [0.0, 250.0, 250.0]
    assert result.unit_switch_penalty == pytest.approx(500.0)


def test_early_switch_penalty_discourages_short_operating_states(
    config: CascadeConfig,
) -> None:
    dwell_config = replace(
        config,
        unit_switch_penalty_weight=0.0,
        minimum_state_duration_hours=3,
        early_switch_penalty_weight=100.0,
    )
    requested = np.zeros((2, 3))
    requested[0, 1] = dwell_config.plants[0].min_flow_m3s

    result = simulate_cascade(dwell_config, np.zeros((2, 3)), requested)

    assert result.state_duration_hours[0].tolist() == [1, 1, 1]
    assert result.early_switch_penalty_by_period[0].tolist() == [0.0, 200.0, 200.0]
    assert result.early_switch_penalty == pytest.approx(400.0)
    assert result.objective == pytest.approx(
        -result.energy_mwh
        + result.level_penalty
        + result.unit_switch_penalty
        + result.early_switch_penalty
    )


def test_downstream_level_and_head_follow_defluence(config: CascadeConfig) -> None:
    requested = np.zeros((2, 3))
    requested[0, 0] = config.plants[0].min_flow_m3s
    result = simulate_cascade(config, np.zeros((2, 3)), requested)
    plant = config.plants[0]
    normalized_defluence = result.defluent_flow_m3s[0, 0] / plant.max_flow_m3s
    expected_downstream = plant.downstream_base_level_m + (
        plant.downstream_level_range_m
        * np.polynomial.polynomial.polyval(
            normalized_defluence, plant.downstream_level_coefficients
        )
    )
    assert result.downstream_level_m[0, 0] == pytest.approx(expected_downstream)
    assert result.net_head_m[0, 0] == pytest.approx(
        result.level_m[0, 0] - expected_downstream
    )


def test_spill_is_blocked_when_provisional_level_is_not_above_maximum(
    config: CascadeConfig,
) -> None:
    result = simulate_cascade(config, np.zeros((2, 3)), np.zeros((2, 3)))
    assert np.allclose(result.spill_flow_m3s, 0.0)
    assert np.allclose(result.sanitary_spill_flow_m3s, 0.0)


def test_mass_balance_includes_fixed_sanitary_spill(config: CascadeConfig) -> None:
    inflows = np.full((2, 3), 20.0)
    result = simulate_cascade(config, inflows, np.zeros((2, 3)))
    stored_variation = np.diff(result.volume_hm3, axis=1)
    expected_variation = config.flow_to_volume_hm3 * (
        result.total_inflow_m3s - result.defluent_flow_m3s
    )
    assert np.allclose(stored_variation, expected_variation)


def test_gradual_spill_uses_the_maximorum_storage_band(config: CascadeConfig) -> None:
    narrow_plant_a = replace(
        config.plants[0], max_volume_hm3=1.01, maximorum_volume_hm3=1.10
    )
    narrow_config = CascadeConfig(
        (narrow_plant_a, config.plants[1]), 3, 1.0, 1, 1000.0
    )
    inflows = np.array([[20.0, 20.0, 20.0], [0.0, 0.0, 0.0]])
    result = simulate_cascade(narrow_config, inflows, np.zeros((2, 3)))
    for plant_index, plant in enumerate(narrow_config.plants):
        assert np.all(result.volume_hm3[plant_index] <= plant.maximorum_volume_hm3)
    assert np.any(result.level_control_spill_flow_m3s > 0.0)


def test_upstream_curve_preserves_bounds_and_is_nonlinear(config: CascadeConfig) -> None:
    result = simulate_cascade(config, np.zeros((2, 3)), np.zeros((2, 3)))
    assert config.plants[0].min_level_m < result.level_m[0, 0] < config.plants[0].max_level_m


def test_maximorum_level_branch_is_monotonic_and_anchored(config: CascadeConfig) -> None:
    plant = config.plants[0]
    middle_volume = (plant.max_volume_hm3 + plant.maximorum_volume_hm3) / 2.0

    assert upstream_level(plant, plant.max_volume_hm3) == pytest.approx(
        plant.max_level_m
    )
    assert plant.max_level_m < upstream_level(plant, middle_volume) < plant.maximorum_level_m
    assert upstream_level(plant, plant.maximorum_volume_hm3) == pytest.approx(
        plant.maximorum_level_m
    )
    assert level_control_spill(plant, plant.max_level_m) == 0.0
    assert level_control_spill(plant, 111.0) > 0.0


def test_power_respects_operating_limits(config: CascadeConfig) -> None:
    requested = np.full((2, 3), 1_000.0)
    result = simulate_cascade(config, np.full((2, 3), 1_000.0), requested)
    minimum = np.array([[1.0], [1.0]])
    maximum = np.array([[10.0], [10.0]])
    assert np.all(result.power_mw <= maximum)
    assert np.all((result.power_mw == 0.0) | (result.power_mw >= minimum))


def test_actual_head_keeps_enabled_power_above_minimum(
    config: CascadeConfig,
) -> None:
    lower_head_plant_a = replace(
        config.plants[0],
        initial_volume_hm3=0.6,
        downstream_base_level_m=95.0,
        downstream_level_range_m=0.0,
    )
    lower_head_config = CascadeConfig(
        (lower_head_plant_a, config.plants[1]), 3, 1.0, 1, 1000.0
    )
    requested = np.zeros((2, 3))
    requested[0, 0] = lower_head_plant_a.min_flow_m3s

    result = simulate_cascade(lower_head_config, np.zeros((2, 3)), requested)

    assert result.turbine_flow_m3s[0, 0] > lower_head_plant_a.min_flow_m3s
    assert result.power_mw[0, 0] >= lower_head_plant_a.min_power_mw - 1e-8


@pytest.mark.parametrize("fraction", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_power_schedule_inversion_tracks_feasible_targets(
    config: CascadeConfig, fraction: float
) -> None:
    """Invert minimum, intermediate and maximum feasible targets."""
    feasible_plants = tuple(
        replace(
            plant,
            downstream_base_level_m=(
                upstream_level(plant, plant.initial_volume_hm3) - plant.head_m
            ),
            downstream_level_range_m=0.0,
        )
        for plant in config.plants
    )
    feasible_config = replace(
        config, plants=(feasible_plants[0], feasible_plants[1]), periods=1
    )
    target = np.vstack(
        [
            np.full(
                feasible_config.periods,
                plant.min_power_mw
                + fraction * (plant.max_power_mw - plant.min_power_mw),
            )
            for plant in feasible_config.plants
        ]
    )
    result = simulate_power_schedule(feasible_config, np.zeros((2, 1)), target)

    assert np.allclose(result.delivered_power_mw, target, atol=1e-6)
    assert np.all(result.power_deficit_mw <= 1e-6)
    assert np.all(result.dispatch_status == "met")


def test_power_schedule_zero_target_keeps_units_off(config: CascadeConfig) -> None:
    result = simulate_power_schedule(config, np.zeros((2, 3)), np.zeros((2, 3)))

    assert np.all(result.delivered_power_mw == 0.0)
    assert np.all(result.dispatch_status == "off")


def test_power_schedule_rejects_target_between_zero_and_minimum(
    config: CascadeConfig,
) -> None:
    target = np.zeros((2, 3))
    target[0, 0] = config.plants[0].min_power_mw / 2.0

    with pytest.raises(ValueError, match="must be zero"):
        simulate_power_schedule(config, np.zeros((2, 3)), target)


def test_power_schedule_records_water_limited_deficit(config: CascadeConfig) -> None:
    water_limited_config = replace(config, period_hours=100_000.0)
    target = np.vstack(
        [
            np.full(water_limited_config.periods, plant.max_power_mw)
            for plant in water_limited_config.plants
        ]
    )
    result = simulate_power_schedule(
        water_limited_config, np.zeros((2, 3)), target
    )

    assert np.any(result.power_deficit_mw > 0.0)
    assert "water_limited" in result.dispatch_status
    assert np.all(
        (result.delivered_power_mw == 0.0)
        | (result.delivered_power_mw >= np.array([[1.0], [1.0]]) - 1e-6)
    )
