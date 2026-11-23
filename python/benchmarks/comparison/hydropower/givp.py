# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""GIVP adapter for the synthetic-hydropower comparison.

GIVP enforces ``max_evaluations`` itself and counts only real objective calls;
cache hits do not consume the physical-evaluation budget.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

import numpy as np
from numpy.typing import NDArray

from benchmarks.comparison.hydropower.budget import (
    SearchResult,
    boolean,
    integer,
    number,
    optional_integer,
)
from givp import GIVPConfig, givp
from givp.examples.synthetic_hydropower.optimization import (
    OptimizationDefinition,
    project_power_vector,
)

ABLATION_VARIANTS = ("current", "groups", "repair", "multiscale", "combined")


def run_givp(
    objective: Callable[[NDArray[np.float64]], float],
    definition: OptimizationDefinition,
    profile: Mapping[str, object],
    seed: int | None,
) -> SearchResult:
    """Minimize ``objective`` with the profile's GIVP configuration."""
    variant = str(profile.get("ablation_variant", "combined"))
    if variant not in ABLATION_VARIANTS:
        raise ValueError(f"unsupported GIVP ablation variant: {variant!r}")
    use_groups = variant in {"groups", "combined"}
    use_repair = variant in {"repair", "combined"}
    use_multiscale = variant in {"multiscale", "combined"}
    config = GIVPConfig(
        max_iterations=integer(profile, "max_iterations"),
        alpha=number(profile, "alpha"),
        vnd_iterations=integer(profile, "vnd_iterations"),
        ils_iterations=integer(profile, "ils_iterations"),
        perturbation_strength=integer(profile, "perturbation_strength"),
        use_elite_pool=boolean(profile, "use_elite_pool"),
        elite_size=integer(profile, "elite_size"),
        path_relink_frequency=integer(profile, "path_relink_frequency"),
        adaptive_alpha=boolean(profile, "adaptive_alpha"),
        alpha_min=number(profile, "alpha_min"),
        alpha_max=number(profile, "alpha_max"),
        num_candidates_per_step=integer(profile, "num_candidates_per_step"),
        use_cache=boolean(profile, "use_cache"),
        cache_size=integer(profile, "cache_size"),
        early_stop_threshold=integer(profile, "early_stop_threshold"),
        use_convergence_monitor=boolean(profile, "use_convergence_monitor"),
        n_workers=integer(profile, "n_workers"),
        time_limit=number(profile, "time_limit_seconds"),
        max_evaluations=optional_integer(profile, "max_evaluations") or 0,
        group_size=24 if use_groups else None,
        continuous_move_scales=(0.05, 0.15, 0.35) if use_multiscale else (0.05,),
        direction="minimize",
    )
    result = givp(
        objective,
        definition.bounds,
        config=config,
        repair=(lambda values: project_power_vector(values, definition).reshape(-1))
        if use_repair
        else None,
        seed=seed,
    )
    return SearchResult(
        np.asarray(result.x, dtype=np.float64),
        float(result.fun),
        int(result.nit),
        int(result.nfev),
        str(result.meta.get("termination_reason", "unknown")),
    )
