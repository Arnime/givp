# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Canonical benchmark problem and algorithm registries."""

from __future__ import annotations

import givp.examples.benchmark as bm
from benchmarks.common.models import ProblemSpec

PROBLEM_REGISTRY: dict[str, ProblemSpec] = {
    "Sphere": {
        "func": bm.sphere,
        "bounds_factory": lambda n: [(-5.12, 5.12)] * n,
        "optimum": 0.0,
        "reference": "De Jong (1975)",
    },
    "Rosenbrock": {
        "func": bm.rosenbrock,
        "bounds_factory": lambda n: [(-5.0, 10.0)] * n,
        "optimum": 0.0,
        "reference": "Rosenbrock (1960)",
    },
    "Rastrigin": {
        "func": bm.rastrigin,
        "bounds_factory": lambda n: [(-5.12, 5.12)] * n,
        "optimum": 0.0,
        "reference": "Rastrigin (1974); Mühlenbein et al. (1991)",
    },
    "Ackley": {
        "func": bm.ackley,
        "bounds_factory": lambda n: [(-32.768, 32.768)] * n,
        "optimum": 0.0,
        "reference": "Ackley (1987)",
    },
    "Griewank": {
        "func": bm.griewank,
        "bounds_factory": lambda n: [(-600.0, 600.0)] * n,
        "optimum": 0.0,
        "reference": "Griewank (1981)",
    },
    "Schwefel": {
        "func": bm.schwefel,
        "bounds_factory": lambda n: [(-500.0, 500.0)] * n,
        "optimum": 0.0,
        "reference": "Schwefel (1981)",
    },
}

ALGO_DESCRIPTIONS = {
    "GIVP-full": "GRASP-ILS-VND-PR -- full hybrid pipeline (this work)",
    "GIVP-tuned": "GRASP-ILS-VND-PR -- Optuna-tuned hyperparameters",
    "GRASP-only": "GRASP-only baseline (Feo & Resende 1995)",
    "DE": "Differential Evolution -- scipy.optimize (Storn & Price 1997)",
    "PSO": "Particle Swarm Optimization -- pymoo (Kennedy & Eberhart 1995)",
    "GA": "Genetic Algorithm -- pymoo (Holland 1975)",
    "CMA-ES": "Covariance Matrix Adaptation Evolution Strategy -- pymoo (Hansen & Ostermeier 2001)",
    "SA": "Dual Annealing -- scipy.optimize (Xiang et al. 1997)",
}
