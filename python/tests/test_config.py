# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Tests covering ``GIVPConfig`` validation and direction logic."""

from __future__ import annotations

from typing import Any, cast

import pytest
from givp import GIVPConfig, InvalidConfigError


def test_default_config_is_valid() -> None:
    cfg = GIVPConfig()
    assert cfg.minimize is True
    assert cfg.direction == "minimize"


def test_minimize_false_sets_direction_maximize() -> None:
    cfg = GIVPConfig(minimize=False)
    assert cfg.direction == "maximize"


def test_minimize_true_sets_direction_minimize() -> None:
    cfg = GIVPConfig(minimize=True, direction="maximize")
    assert cfg.minimize is True
    assert cfg.direction == "minimize"


def test_direction_maximize_sets_minimize_false() -> None:
    cfg = GIVPConfig(direction="maximize")
    assert cfg.minimize is False


def test_invalid_direction_raises_invalid_config() -> None:
    with pytest.raises(InvalidConfigError):
        GIVPConfig(direction="bogus")  # type: ignore[arg-type]


def test_invalid_path_relink_strategy_raises_invalid_config() -> None:
    with pytest.raises(InvalidConfigError):
        GIVPConfig(path_relink_strategy="invalid")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_iterations", 0),
        ("vnd_iterations", 0),
        ("ils_iterations", 0),
        ("elite_size", 0),
        ("path_relink_frequency", 0),
        ("num_candidates_per_step", 0),
        ("cache_size", 0),
        ("early_stop_threshold", 0),
        ("n_workers", 0),
    ],
)
def test_positive_int_fields_reject_zero(field: str, value: int) -> None:
    with pytest.raises(InvalidConfigError):
        GIVPConfig(**cast(dict[str, Any], {field: value}))


def test_perturbation_strength_negative_rejected() -> None:
    with pytest.raises(InvalidConfigError):
        GIVPConfig(perturbation_strength=-1)


@pytest.mark.parametrize("alpha", [-0.1, 1.1, 2.0])
def test_alpha_out_of_range_rejected(alpha: float) -> None:
    with pytest.raises(InvalidConfigError):
        GIVPConfig(alpha=alpha)


def test_alpha_min_greater_than_alpha_max_rejected() -> None:
    with pytest.raises(InvalidConfigError):
        GIVPConfig(alpha_min=0.5, alpha_max=0.1)


@pytest.mark.parametrize("field", ["alpha_min", "alpha_max"])
def test_alpha_bounds_out_of_range_rejected(field: str) -> None:
    with pytest.raises(InvalidConfigError):
        GIVPConfig(**cast(dict[str, Any], {field: 1.5}))


def test_time_limit_negative_rejected() -> None:
    with pytest.raises(InvalidConfigError):
        GIVPConfig(time_limit=-1.0)


def test_integer_split_negative_rejected() -> None:
    with pytest.raises(InvalidConfigError):
        GIVPConfig(integer_split=-1)


def test_integer_split_none_allowed() -> None:
    cfg = GIVPConfig(integer_split=None)
    assert cfg.integer_split is None


def test_integer_split_positive_allowed() -> None:
    cfg = GIVPConfig(integer_split=2)
    assert cfg.integer_split == 2


def test_as_core_config_copies_fields() -> None:
    cfg = GIVPConfig(max_iterations=7, alpha=0.3)
    core_cfg = cfg.as_core_config()
    assert core_cfg.max_iterations == 7
    assert core_cfg.alpha == pytest.approx(0.3)
