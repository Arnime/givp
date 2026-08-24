"""Unit tests for deterministic benchmark adapters and optimizer orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

import givp.examples.synthetic_hydropower.runner as runner_module
from givp.examples.synthetic_hydropower.benchmark.cases import (
    PowerCase,
    build_power_cases,
    power_levels,
)
from givp.examples.synthetic_hydropower.benchmark.definition import (
    DeterministicDefinition,
)
from givp.examples.synthetic_hydropower.benchmark.deterministic.execution import (
    DeterministicRun,
)
from givp.examples.synthetic_hydropower.benchmark.deterministic.frames import (
    balance_summary_frame,
    balance_time_series_frame,
    inflow_frame,
    schedule_frame,
)
from givp.examples.synthetic_hydropower.benchmark.deterministic.persistence import (
    save_deterministic_benchmark,
)
from givp.examples.synthetic_hydropower.model import (
    CascadeConfig,
    PlantConfig,
    PowerScheduleResult,
    SimulationResult,
)


def _plant(name: str, *, level_offset: float = 0.0) -> PlantConfig:
    """Create a compact fictional plant for isolated unit tests."""
    return PlantConfig(
        name=name,
        initial_volume_hm3=1.0,
        min_volume_hm3=0.5,
        max_volume_hm3=1.5,
        maximorum_volume_hm3=1.7,
        min_level_m=100.0 + level_offset,
        max_level_m=110.0 + level_offset,
        head_m=50.0,
        efficiency=0.9,
        min_power_mw=1.0,
        max_power_mw=5.0,
        upstream_level_coefficients=[0.0, 1.0, 0.0, 0.0, 0.0],
        downstream_base_level_m=50.0,
        downstream_level_range_m=4.0,
        downstream_level_coefficients=[0.0, 1.0, 0.0, 0.0, 0.0],
        sanitary_spill_flow_m3s=0.25,
        spill_response=0.6,
        spill_response_exponent=1.3,
        maximorum_level_m=112.0 + level_offset,
    )


def _cascade() -> CascadeConfig:
    """Create a two-period cascade suitable for tabular unit tests."""
    return CascadeConfig((_plant("A"), _plant("B", level_offset=-20.0)), 2, 1.0, 1, 1.0)


def _simulation(cascade: CascadeConfig) -> SimulationResult:
    """Create a complete, deterministic simulation value object."""
    shape = (2, cascade.periods)
    flows = np.full(shape, 2.0)
    volumes = np.array([[1.0, 1.0, 1.0], [1.0, 1.0, 1.0]])
    levels = np.array([[105.0, 99.0, 111.0], [85.0, 86.0, 87.0]])
    zeros = np.zeros(shape)
    return SimulationResult(
        requested_flow_m3s=flows,
        turbine_flow_m3s=flows,
        spill_flow_m3s=zeros,
        sanitary_spill_flow_m3s=zeros,
        capacity_spill_flow_m3s=zeros,
        level_control_spill_flow_m3s=zeros,
        inflow_m3s=flows,
        total_inflow_m3s=flows,
        upstream_arrival_m3s=zeros,
        volume_hm3=volumes,
        level_m=levels,
        downstream_level_m=np.full(shape, 50.0),
        net_head_m=np.full(shape, 50.0),
        defluent_flow_m3s=flows,
        power_mw=np.full(shape, 1.0),
        energy_mwh=4.0,
        unit_on=np.ones(shape, dtype=np.bool_),
        state_duration_hours=np.ones(shape, dtype=np.int_),
        unit_switch_penalty_by_period=zeros,
        unit_switch_penalty=0.0,
        early_switch_penalty_by_period=zeros,
        early_switch_penalty=0.0,
        minimum_level_penalty_by_period=zeros,
        maximum_level_penalty_by_period=zeros,
        minimum_level_penalty=1.0,
        maximum_level_penalty=2.0,
        level_penalty=3.0,
        objective=-1.0,
    )


def _run(cascade: CascadeConfig) -> DeterministicRun:
    """Create zero and nonzero cases to exercise both summary branches."""
    zero_target = np.zeros((2, cascade.periods))
    on_target = np.ones((2, cascade.periods))
    cases = (
        PowerCase("case-off", "scenario", "off", "off", zero_target),
        PowerCase("case-on", "scenario", "minimum", "minimum", on_target),
    )
    simulation = _simulation(cascade)
    results = {
        "case-off": PowerScheduleResult(
            simulation, zero_target, zero_target, zero_target, np.full((2, 2), "off")
        ),
        "case-on": PowerScheduleResult(
            simulation, on_target, on_target, zero_target, np.full((2, 2), "delivered")
        ),
    }
    return DeterministicRun(
        inflows={"scenario": np.full((2, cascade.periods), 2.0)},
        cases=cases,
        results=results,
    )


def test_power_cases_form_the_documented_factorial_matrix() -> None:
    """Build all six-by-six constant schedules from plant power bounds."""
    cascade = _cascade()

    levels = power_levels(cascade.plants[0])
    cases = build_power_cases(cascade, "scenario")

    assert levels["off"] == 0.0
    assert levels["minimum"] == 1.0
    assert levels["maximum"] == 5.0
    assert len(cases) == 36
    assert all(case.target_power_mw.shape == (2, 2) for case in cases)


def test_deterministic_frames_cover_inputs_hourly_results_and_summary() -> None:
    """Convert compact value objects into every canonical table schema."""
    cascade = _cascade()
    run = _run(cascade)

    inflows = inflow_frame(run.inflows)
    schedules = schedule_frame(run.cases)
    time_series = balance_time_series_frame(run.cases, run.results, cascade)
    summary = balance_summary_frame(run.cases, run.results, cascade)

    assert inflows.shape[0] == 4
    assert schedules.shape[0] == 8
    assert time_series.shape[0] == 8
    assert np.allclose(time_series["mass_balance_residual_hm3"], 0.0)
    assert summary.shape[0] == 2
    assert summary.loc[summary["case_id"] == "case-off", "delivered_percent"].item() == 100.0
    assert summary.loc[summary["case_id"] == "case-on", "delivered_percent"].item() == 100.0
    assert summary["plant_a_hours_below_minimum"].max() == 1
    assert summary["plant_a_hours_above_maximum"].max() == 1


def test_deterministic_persistence_writes_protocol_and_suite_manifests(
    tmp_path: Path,
) -> None:
    """Persist one compact run, including an optional reference figure."""
    cascade = _cascade()
    run = _run(cascade)
    definition = DeterministicDefinition(
        benchmark_id="unit-benchmark",
        cascade=cascade,
        scenarios=(),
        decimal_places=6,
        comparison_tolerance=1e-6,
    )
    benchmark_dir = tmp_path / "benchmark"
    config_path = benchmark_dir / "config" / "base.json"
    definition_path = benchmark_dir / "protocols" / "deterministic_balance" / "definition.json"
    provenance_path = benchmark_dir / "data_provenance.json"
    figure_path = benchmark_dir / "protocols" / "deterministic_balance" / "figures" / "reference.png"
    for path in (config_path, definition_path, provenance_path, figure_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"{}" if path.suffix == ".json" else b"png")

    checksums = save_deterministic_benchmark(
        run,
        definition,
        benchmark_dir,
        config_path,
        definition_path,
        provenance_path,
    )

    protocol_manifest = json.loads(
        (benchmark_dir / "protocols" / "deterministic_balance" / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    suite_manifest = json.loads(
        (benchmark_dir / "benchmark_manifest.json").read_text(encoding="utf-8")
    )
    assert protocol_manifest["case_count"] == 2
    assert protocol_manifest["balance_time_series_rows"] == 8
    assert "protocols/deterministic_balance/figures/reference.png" in checksums
    assert suite_manifest["protocols"] == ["deterministic_balance"]


def test_runner_loads_split_configuration_and_uses_optimizer_as_dependency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep optimizer orchestration unit-scoped by replacing external execution."""
    cascade = _cascade()
    config_path = tmp_path / "base.json"
    definition_path = tmp_path / "definition.json"
    config_path.write_text(
        json.dumps({"plants": [plant.__dict__ for plant in cascade.plants]}),
        encoding="utf-8",
    )
    definition_path.write_text(
        json.dumps(
            {
                "cascade": {
                    "periods": 2,
                    "period_hours": 1.0,
                    "travel_time_steps": 1,
                    "level_penalty_weight": 1.0,
                },
                "optimizer": {
                    "max_iterations": 1,
                    "vnd_iterations": 1,
                    "ils_iterations": 1,
                },
                "scenarios": [
                    {
                        "name": "scenario",
                        "upstream_base": 2.0,
                        "downstream_base": 1.0,
                        "variability": 0.0,
                        "profile": "stable",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    experiment = runner_module.load_experiment_config(config_path, definition_path)
    simulated = SimpleNamespace(objective=-1.0)
    calls: list[np.ndarray] = []

    def fake_simulate(
        _cascade_config: CascadeConfig,
        _inflows: np.ndarray,
        requested: np.ndarray,
    ) -> Any:
        calls.append(requested.copy())
        return simulated

    def fake_givp(objective: Any, *, bounds: Any, config: Any, seed: int) -> Any:
        vector = np.zeros(len(bounds))
        assert objective(vector) == -1.0
        assert config.direction == "minimize"
        assert seed == 7
        return SimpleNamespace(x=vector)

    monkeypatch.setattr(runner_module, "generate_inflows", lambda *_args: np.ones((2, 2)))
    monkeypatch.setattr(runner_module, "simulate_cascade", fake_simulate)
    monkeypatch.setattr(runner_module, "givp", fake_givp)

    result = runner_module.optimize_scenario(experiment, "scenario", seed=7)

    assert result is simulated
    assert len(calls) == 2
    with pytest.raises(ValueError, match="unknown scenario"):
        runner_module.optimize_scenario(experiment, "missing", seed=7)
