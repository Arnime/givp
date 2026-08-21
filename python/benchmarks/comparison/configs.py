# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""GIVP benchmark configurations."""

import dataclasses

from givp import GIVPConfig


def _config_givp_full(max_iter: int, time_limit: float) -> GIVPConfig:
    """Full GIVP pipeline: adaptive alpha, ILS, VND, elite pool, path relinking."""
    return GIVPConfig(
        max_iterations=max_iter,
        alpha=0.12,
        adaptive_alpha=True,
        alpha_min=0.08,
        alpha_max=0.18,
        vnd_iterations=200,
        ils_iterations=10,
        perturbation_strength=4,
        use_elite_pool=True,
        elite_size=7,
        path_relink_frequency=8,
        use_cache=True,
        cache_size=10_000,
        early_stop_threshold=80,
        use_convergence_monitor=True,
        time_limit=time_limit,
    )


def _config_grasp_only(max_iter: int, time_limit: float) -> GIVPConfig:
    """GRASP-only baseline (Feo & Resende, 1995).

    Disables ILS, VND depth, elite pool, convergence monitor and path
    relinking to reproduce the plain GRASP construction + trivial descent.
    """
    return GIVPConfig(
        max_iterations=max_iter,
        alpha=0.12,
        adaptive_alpha=False,
        vnd_iterations=1,
        ils_iterations=1,
        perturbation_strength=0,
        use_elite_pool=False,
        use_convergence_monitor=False,
        use_cache=True,
        cache_size=10_000,
        early_stop_threshold=max_iter,
        time_limit=time_limit,
    )


def _config_givp_tuned(
    base: GIVPConfig,
    max_iter: int,
    time_limit: float,
) -> GIVPConfig:
    """Return a copy of *base* with max_iterations and time_limit overridden."""
    return dataclasses.replace(base, max_iterations=max_iter, time_limit=time_limit)
