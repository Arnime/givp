# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Scikit-learn-compatible object-oriented GIVP interface."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray
from sklearn.base import BaseEstimator

from givp.api.functional import givp
from givp.api.types import BoundsLike, IterationCallback, ObjectiveFn
from givp.api.validation import _resolve_direction
from givp.config import GIVPConfig
from givp.result import OptimizeResult


class GIVPOptimizer(BaseEstimator):
    """Object-oriented optimizer compatible with scikit-learn estimators."""

    def __init__(
        self,
        func: ObjectiveFn,
        bounds: BoundsLike,
        *,
        num_vars: int | None = None,
        minimize: bool | None = None,
        direction: str | None = None,
        config: GIVPConfig | None = None,
        initial_guess: Sequence[float] | None = None,
        initial_guesses: Sequence[Sequence[float]] | None = None,
        iteration_callback: IterationCallback | None = None,
        seed: int | None = None,
        verbose: bool = False,
    ) -> None:
        self.func = func
        self.bounds = bounds
        self.num_vars = num_vars
        self.direction = _resolve_direction(minimize, direction)
        self.minimize = self.direction == "minimize"
        self.config = config or GIVPConfig()
        self.initial_guess = initial_guess
        self.initial_guesses = initial_guesses
        self.iteration_callback = iteration_callback
        self.seed = seed
        self.verbose = verbose

        self.best_x: NDArray[np.float64] | None = None
        self.best_fun = float("-inf") if self.direction == "maximize" else float("inf")
        self.history: list[OptimizeResult] = []

    def _is_better(self, candidate: float) -> bool:
        """Return whether a candidate improves the historical best value."""
        if self.direction == "maximize":
            return candidate > self.best_fun
        return candidate < self.best_fun

    def run(self) -> OptimizeResult:
        """Execute one optimization round and update the historical best."""
        result = givp(
            self.func,
            self.bounds,
            num_vars=self.num_vars,
            minimize=self.minimize,
            config=self.config,
            initial_guess=self.initial_guess,
            initial_guesses=self.initial_guesses,
            iteration_callback=self.iteration_callback,
            seed=self.seed,
            verbose=self.verbose,
        )
        self.history.append(result)
        if self.best_x is None or self._is_better(result.fun):
            self.best_x = result.x
            self.best_fun = result.fun
        return result

    def fit(
        self, _x: NDArray | None = None, _y: NDArray | None = None
    ) -> GIVPOptimizer:
        """Run the optimizer and return ``self`` for sklearn compatibility."""
        self.run()
        return self
