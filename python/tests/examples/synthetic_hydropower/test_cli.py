"""Tests for the synthetic hydropower command-line path boundary."""

from pathlib import Path

import pytest

from givp.examples.synthetic_hydropower.paths import (
    default_config_path,
    default_output_dir,
    validate_cli_paths,
)


def test_cli_paths_accept_only_benchmark_owned_locations() -> None:
    """Accept CLI arguments when both paths belong to the benchmark."""
    validate_cli_paths(default_config_path(), default_output_dir())


@pytest.mark.parametrize("untrusted_argument", ["config", "output"])
def test_cli_paths_reject_untrusted_locations(
    tmp_path: Path, untrusted_argument: str
) -> None:
    """Reject arbitrary read and write paths supplied to the console command."""
    untrusted_config = tmp_path / "config.json"
    untrusted_config.write_text("{}", encoding="utf-8")
    config_path = (
        untrusted_config
        if untrusted_argument == "config"
        else default_config_path()
    )
    output_dir = (
        tmp_path / "output"
        if untrusted_argument == "output"
        else default_output_dir()
    )

    with pytest.raises(ValueError, match="CLI"):
        validate_cli_paths(config_path, output_dir)
