"""Facade for reproducible optimization benchmark examples."""

from givp.examples.benchmark.ackley import ackley
from givp.examples.benchmark.cubic import constrained_cubic
from givp.examples.benchmark.griewank import griewank
from givp.examples.benchmark.knapsack import knapsack_dp, knapsack_penalty
from givp.examples.benchmark.qap import qap_cost
from givp.examples.benchmark.rastrigin import rastrigin
from givp.examples.benchmark.rosenbrock import rosenbrock
from givp.examples.benchmark.schwefel import schwefel
from givp.examples.benchmark.sphere import sphere
from givp.examples.benchmark.sweep import seed_sweep, sweep_summary

__all__ = [
    "ackley",
    "constrained_cubic",
    "griewank",
    "knapsack_dp",
    "knapsack_penalty",
    "qap_cost",
    "rastrigin",
    "rosenbrock",
    "schwefel",
    "seed_sweep",
    "sphere",
    "sweep_summary",
]
