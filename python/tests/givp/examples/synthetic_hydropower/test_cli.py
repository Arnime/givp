"""Tests for the synthetic hydropower command-line boundary."""

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import givp.examples.synthetic_hydropower.cli as cli_module
from givp.examples.synthetic_hydropower.paths import (
    default_config_path,
    default_definition_path,
    default_output_dir,
    validate_cli_paths,
)


def test_cli_paths_accept_only_benchmark_owned_locations() -> None:
    """Accept CLI arguments when both paths belong to the benchmark."""
    validate_cli_paths(
        default_config_path(), default_definition_path(), default_output_dir()
    )


@pytest.mark.parametrize("untrusted_argument", ["config", "definition", "output"])
def test_cli_paths_reject_untrusted_locations(
    tmp_path: Path, untrusted_argument: str
) -> None:
    """Reject arbitrary read and write paths supplied to the console command."""
    untrusted_config = tmp_path / "config.json"
    untrusted_config.write_text("{}", encoding="utf-8")
    config_path = (
        untrusted_config if untrusted_argument == "config" else default_config_path()
    )
    definition_path = (
        untrusted_config
        if untrusted_argument == "definition"
        else default_definition_path()
    )
    output_dir = (
        tmp_path / "output" if untrusted_argument == "output" else default_output_dir()
    )

    with pytest.raises(ValueError, match="CLI"):
        validate_cli_paths(config_path, definition_path, output_dir)


def test_cli_writes_scenario_series_and_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the complete CLI boundary with a deterministic simulated result."""
    config_path = tmp_path / "base.json"
    definition_path = tmp_path / "definition.json"
    output_dir = tmp_path / "output"
    config_path.write_text("{}", encoding="utf-8")
    definition_path.write_text("{}", encoding="utf-8")
    experiment = SimpleNamespace(
        scenarios={"case": object()},
        cascade=SimpleNamespace(periods=2),
    )
    result = SimpleNamespace(
        inflow_m3s=np.full((2, 2), 10.0),
        total_inflow_m3s=np.full((2, 2), 11.0),
        upstream_arrival_m3s=np.full((2, 2), 1.0),
        power_mw=np.full((2, 2), 5.0),
        turbine_flow_m3s=np.full((2, 2), 4.0),
        spill_flow_m3s=np.full((2, 2), 2.0),
        sanitary_spill_flow_m3s=np.full((2, 2), 0.5),
        capacity_spill_flow_m3s=np.full((2, 2), 0.75),
        level_control_spill_flow_m3s=np.full((2, 2), 0.75),
        defluent_flow_m3s=np.full((2, 2), 6.0),
        level_m=np.full((2, 3), 100.0),
        downstream_level_m=np.full((2, 2), 50.0),
        net_head_m=np.full((2, 2), 50.0),
        energy_mwh=20.0,
        level_penalty=0.0,
        objective=-20.0,
    )
    monkeypatch.setattr(cli_module, "validate_cli_paths", lambda *_args: None)
    monkeypatch.setattr(cli_module, "default_config_path", lambda: config_path)
    monkeypatch.setattr(cli_module, "default_definition_path", lambda: definition_path)
    monkeypatch.setattr(cli_module, "default_output_dir", lambda: output_dir)
    monkeypatch.setattr(
        cli_module,
        "load_experiment_config",
        lambda *_args: experiment,
    )
    monkeypatch.setattr(cli_module, "optimize_scenario", lambda *_args: result)
    monkeypatch.setattr(
        "sys.argv",
        [
            "synthetic-hydropower",
            "--config",
            str(config_path),
            "--definition",
            str(definition_path),
            "--output-dir",
            str(output_dir),
            "--seed",
            "7",
        ],
    )

    cli_module.main()

    scenario = (output_dir / "case.csv").read_text(encoding="utf-8")
    summary = (output_dir / "summary.json").read_text(encoding="utf-8")
    assert len(scenario.splitlines()) == 3
    assert '"scenario": "case"' in summary
    assert '"energy_mwh": 20.0' in summary


def test_balance_command_writes_a_json_protocol_response(tmp_path: Path) -> None:
    """Evaluate an arbitrary canonical-horizon schedule outside benchmark paths."""
    request_path = tmp_path / "request.json"
    output_path = tmp_path / "response.json"
    request_path.write_text(
        json.dumps(
            {
                "schema_version": "synthetic-hydropower/v1",
                "requests": [
                    {
                        "case_id": "off",
                        "incremental_inflow_m3s": [[0.0] * 24, [0.0] * 24],
                        "target_power_mw": [[0.0] * 24, [0.0] * 24],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    cli_module.main(
        ["balance", "--request", str(request_path), "--output", str(output_path)]
    )

    response = json.loads(output_path.read_text(encoding="utf-8"))
    assert response["schema_version"] == "synthetic-hydropower/v1"
    assert response["results"][0]["case_id"] == "off"
