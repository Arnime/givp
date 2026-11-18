# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Unified Particle Swarm Optimization built on Pymoo's PSO lifecycle."""

from __future__ import annotations

import numpy as np
from pymoo.algorithms.soo.nonconvex.pso import PSO
from pymoo.core.population import Population


class UPSO(PSO):
    """PSO with a ring-local and global best blended by ``unification_factor``.

    The particle update is delegated to Pymoo's PSO implementation.  This class
    changes the social target to ``u * gbest + (1 - u) * lbest`` and applies the
    linearly decreasing inertia schedule used by the former experiment notebooks.
    """

    def __init__(
        self,
        *,
        unification_factor: float = 0.3,
        neighborhood_size: int = 3,
        w_min: float = 0.6,
        w_max: float = 0.9,
        c1: float = 0.6,
        c2: float = 0.4,
        max_generations: int,
        **kwargs: object,
    ) -> None:
        """Initialize the unified swarm variant.

        Args:
            unification_factor: Weight assigned to the global-best component.
            neighborhood_size: Odd ring-neighborhood size for the local best.
            w_min: Inertia weight at the final generation.
            w_max: Inertia weight at the first generation.
            c1: Cognitive coefficient.
            c2: Social coefficient.
            max_generations: Generation budget used for the inertia schedule.
            **kwargs: Parameters forwarded to :class:`pymoo`'s ``PSO``.

        Raises:
            ValueError: If a UPSO hyperparameter is outside its valid range.
        """
        if not 0.0 <= unification_factor <= 1.0:
            raise ValueError("unification_factor must be between zero and one")
        if neighborhood_size < 3 or neighborhood_size % 2 == 0:
            raise ValueError("neighborhood_size must be an odd integer of at least three")
        if w_min < 0.0 or w_max < w_min:
            raise ValueError("inertia weights must satisfy zero <= w_min <= w_max")
        if c1 < 0.0 or c2 < 0.0:
            raise ValueError("acceleration coefficients must be non-negative")
        if max_generations < 1:
            raise ValueError("max_generations must be positive")

        super().__init__(
            adaptive=False,
            w=w_max,
            c1=c1,
            c2=c2,
            pertube_best=False,
            **kwargs,
        )
        self.unification_factor = unification_factor
        self.neighborhood_size = neighborhood_size
        self.w_min = w_min
        self.w_max = w_max
        self.max_generations = max_generations

    def _infill(self) -> Population:
        """Set the scheduled inertia before Pymoo creates the offspring swarm."""
        progress = min(max(self.n_gen - 1, 0), self.max_generations - 1)
        denominator = max(self.max_generations - 1, 1)
        self.w = self.w_max - (self.w_max - self.w_min) * progress / denominator
        return super()._infill()

    def _social_best(self) -> Population:
        """Return the unified global/ring-local social target for every particle."""
        personal_best = self.pop
        positions, values = personal_best.get("X", "F")
        scalar_values = np.asarray(values, dtype=float).reshape(-1)
        particle_count = len(personal_best)
        offsets = np.arange(-(self.neighborhood_size // 2), self.neighborhood_size // 2 + 1)
        neighbors = (np.arange(particle_count)[:, None] + offsets) % particle_count
        local_indices = neighbors[
            np.arange(particle_count), np.argmin(scalar_values[neighbors], axis=1)
        ]
        local_best = positions[local_indices]
        global_best = np.broadcast_to(self.opt[0].X, positions.shape)
        unified_best = (
            self.unification_factor * global_best
            + (1.0 - self.unification_factor) * local_best
        )
        return Population.new(X=unified_best)
