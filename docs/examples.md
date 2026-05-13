# Real-world examples

Four end-to-end recipes you can paste into a script. Each one runs in under
10 seconds with default settings.

## 1. Continuous: Rastrigin (multimodal, 30D)

A classic benchmark that defeats naive gradient methods because it has
hundreds of local minima.

```python
import numpy as np

from givp import GIVPConfig, givp


def rastrigin(x: np.ndarray) -> float:
    n = x.size
    return 10.0 * n + float(np.sum(x**2 - 10.0 * np.cos(2.0 * np.pi * x)))


bounds = [(-5.12, 5.12)] * 30
result = givp(
    rastrigin,
    bounds,
    seed=42,
    config=GIVPConfig(max_iterations=80, ils_iterations=10),
)
print(f"best={result.fun:.4f}  nfev={result.nfev}")
```

## 2. Integer: 0/1 Knapsack

Maximise total value subject to a weight budget. The objective uses a heavy
penalty so infeasible solutions are pushed away naturally.

```python
import numpy as np

from givp import GIVPConfig, givp

values = np.array([60, 100, 120, 80, 30, 70, 45, 90])
weights = np.array([10, 20, 30, 15, 5, 18, 8, 25])
capacity = 60


def knapsack(x: np.ndarray) -> float:
    chosen = np.rint(x).astype(int)
    total_w = float((chosen * weights).sum())
    total_v = float((chosen * values).sum())
    if total_w > capacity:
        return -1e6  # heavy penalty (we are maximizing value)
    return total_v


bounds = [(0.0, 1.0)] * len(values)
result = givp(
    knapsack,
    bounds,
    minimize=False,
    seed=7,
    config=GIVPConfig(integer_split=0, max_iterations=50),
)
print("picked:", np.rint(result.x).astype(int))
print(f"value={result.fun:.0f}")
```

## 3. Mixed continuous + integer: portfolio with discrete lots

Optimize 5 continuous weights *plus* 3 integer "lot counts". `integer_split=5`
tells `givp` that indices ``[5, 6, 7]`` must stay integer.

```python
import numpy as np

from givp import GIVPConfig, givp

rng = np.random.default_rng(0)
mu = rng.uniform(0.05, 0.20, size=5)
cov = np.diag(rng.uniform(0.01, 0.05, size=5))


def portfolio(x: np.ndarray) -> float:
    weights, lots = x[:5], x[5:]
    weights = np.abs(weights)
    weights /= weights.sum() if weights.sum() > 0 else 1.0
    expected_return = float(weights @ mu) + 0.001 * float(np.rint(lots).sum())
    risk = float(weights @ cov @ weights)
    # Sharpe-like: maximize return per unit of risk.
    return expected_return / np.sqrt(risk + 1e-12)


bounds = [(0.0, 1.0)] * 5 + [(0, 10)] * 3
result = givp(
    portfolio,
    bounds,
    minimize=False,
    seed=11,
    config=GIVPConfig(integer_split=5, max_iterations=60),
)
print("weights :", np.round(result.x[:5], 3))
print("lots    :", np.rint(result.x[5:]).astype(int))
print(f"sharpe~ {result.fun:.4f}")
```

## 4. Black-box: hyper-parameter tuning of an ML model

Plug any `cross_val_score` into the objective. Each evaluation can be
expensive, so enable the cache and a wall-clock budget.

```python
import numpy as np
from sklearn.datasets import load_iris
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import cross_val_score

from givp import GIVPConfig, givp

X, y = load_iris(return_X_y=True)


def objective(params: np.ndarray) -> float:
    learning_rate, max_depth, n_estimators = params
    model = GradientBoostingClassifier(
        learning_rate=float(learning_rate),
        max_depth=int(max_depth),
        n_estimators=int(n_estimators),
        random_state=0,
    )
    return float(cross_val_score(model, X, y, cv=3).mean())


# learning_rate continuous, max_depth + n_estimators integer
bounds = [(0.01, 0.5), (2, 10), (10, 200)]
result = givp(
    objective,
    bounds,
    minimize=False,
    seed=2024,
    config=GIVPConfig(
        integer_split=1,
        max_iterations=20,
        time_limit=60.0,
        use_cache=True,
    ),
)
print(f"best CV accuracy: {result.fun:.4f}")
print(f"hyperparams     : lr={result.x[0]:.3f}, depth={int(result.x[1])}, n={int(result.x[2])}")
```

## 5. Multi-objective: weighted-sum scalarization sweep

`givp` is single-objective, but you can optimize multiple goals by combining
them into a scalar objective. A practical baseline is weighted sum:

\[
f_w(x) = w\,f_1(x) + (1-w)\,f_2(x),\quad w \in [0, 1]
\]

The sweep below runs the same problem with different `w` values to expose
trade-offs between objective 1 (distance to target return) and objective 2
(portfolio variance surrogate).

```python
import numpy as np

from givp import GIVPConfig, givp

target_return = 0.08
mu = np.array([0.05, 0.09, 0.12])
cov = np.array(
    [
        [0.020, 0.004, 0.002],
        [0.004, 0.030, 0.006],
        [0.002, 0.006, 0.050],
    ]
)


def project_simplex(v: np.ndarray) -> np.ndarray:
    v = np.clip(v, 0.0, None)
    s = float(v.sum())
    return v / s if s > 0 else np.array([1.0, 0.0, 0.0])


def objectives(x: np.ndarray) -> tuple[float, float]:
    w = project_simplex(x)
    ret = float(w @ mu)
    risk = float(w @ cov @ w)
    obj_return = (ret - target_return) ** 2
    obj_risk = risk
    return obj_return, obj_risk


bounds = [(0.0, 1.0)] * 3
config = GIVPConfig(max_iterations=40, ils_iterations=8)
weights = [0.0, 0.25, 0.5, 0.75, 1.0]

rows: list[tuple[float, float, float, float, np.ndarray]] = []
for alpha in weights:
    def scalarized(x: np.ndarray, a: float = alpha) -> float:
        f1, f2 = objectives(x)
        return a * f1 + (1.0 - a) * f2

    r = givp(scalarized, bounds, seed=123, config=config)
    f1, f2 = objectives(r.x)
    rows.append((alpha, f1, f2, r.fun, project_simplex(r.x)))

print("alpha | obj_return | obj_risk | scalarized | weights")
for alpha, f1, f2, f, w in rows:
    print(f"{alpha:>4.2f} | {f1:>10.6f} | {f2:>8.6f} | {f:>10.6f} | {np.round(w, 3)}")
```

Interpretation tips:

- `alpha -> 1.0`: optimizer prioritizes return-target matching (`obj_return`).
- `alpha -> 0.0`: optimizer prioritizes risk minimization (`obj_risk`).
- Intermediate values produce compromise solutions; this is the first
  approximation of a Pareto front for decision support.

Limitations:

- Weighted sum can miss non-convex Pareto regions.
- Objective scaling matters; normalize terms before production use.
- You should run multiple seeds to evaluate robustness of the compromise set.

## 6. Combinatorial: TSP-like objective via discretization

This example encodes a route permutation indirectly from a continuous vector.
Each position score is optimized in `[0, n-1]`, rounded, then converted into
a permutation using `argsort` (stable tie handling).

```python
import numpy as np

from givp import GIVPConfig, givp

# 6-city symmetric toy distance matrix
dist = np.array(
    [
        [0, 2, 9, 10, 7, 3],
        [2, 0, 6, 4, 3, 8],
        [9, 6, 0, 8, 5, 7],
        [10, 4, 8, 0, 6, 9],
        [7, 3, 5, 6, 0, 4],
        [3, 8, 7, 9, 4, 0],
    ],
    dtype=float,
)


def decode_permutation(x: np.ndarray) -> np.ndarray:
    # Discretize to reinforce combinatorial behavior, then map to a valid route.
    scores = np.rint(np.clip(x, 0.0, dist.shape[0] - 1)).astype(int)
    return np.argsort(scores, kind="mergesort")


def tsp_like_cost(x: np.ndarray) -> float:
    p = decode_permutation(x)
    total = 0.0
    for i in range(len(p)):
        a = int(p[i])
        b = int(p[(i + 1) % len(p)])
        total += float(dist[a, b])
    return total


bounds = [(0.0, float(dist.shape[0] - 1))] * dist.shape[0]
cfg = GIVPConfig(integer_split=dist.shape[0], max_iterations=60, ils_iterations=10)

result = givp(tsp_like_cost, bounds, seed=77, config=cfg)
route = decode_permutation(result.x)

print("route:", route.tolist())
print(f"tour length: {result.fun:.3f}")
```

Interpretation tips:

- The objective is purely combinatorial after decoding, while optimization
  stays in `givp`'s native continuous search space.
- Using continuous search (`integer_split=n`) plus explicit rounding in the
  objective is a robust way to model permutation-style objectives.
- The route is deterministic for a fixed seed and config.

## 7. Warm start: multiple elite seeds

When you already know several promising solutions, pass them as
`initial_guesses`. They are validated against the bounds, deduplicated, and
inserted into the elite pool before the first iteration.

```python
import numpy as np

from givp import GIVPConfig, givp


def sphere(x: np.ndarray) -> float:
    return float(np.sum(x**2))


bounds = [(-3.0, 3.0)] * 4
warm_starts = [
    [0.1, 0.1, 0.1, 0.1],
    [1.0, 0.5, 0.2, 0.0],
    [-0.5, 0.8, -0.2, 0.3],
]

result = givp(
    sphere,
    bounds,
    seed=99,
    config=GIVPConfig(max_iterations=20, elite_size=5),
    initial_guesses=warm_starts,
)

print(f"best={result.fun:.4f}")
print("x=", np.round(result.x, 3))
```

Edge cases:

- Duplicate candidates are rejected before the run starts.
- Each seed must match the problem dimension.
- Each coordinate must lie strictly inside the bounds, just like
  `initial_guess`.

## See also

- [Quickstart](quickstart.md) — minimal first run.
- [Algorithm overview](algorithm.md) — what each component does.
- [Profiling](profiling.md) — measuring and improving performance.

---

## Using the components individually

The four metaheuristic building blocks are importable from `givp.core` and
can be called independently. This is useful when you want to embed one phase
inside your own search loop, test a component in isolation, or build a custom
hybrid.

> **Note:** All components work in *minimization* space. Pass a negated
> objective if you are maximizing.

---

### GRASP — greedy randomized construction

`construct_grasp` samples a pool of candidate solutions and selects
the best one via a Restricted Candidate List (RCL).

```python
import numpy as np
from givp.core.grasp import construct_grasp
from givp.core.helpers import _set_integer_split

def sphere(x: np.ndarray) -> float:
    return float(np.sum(x ** 2))

num_vars = 6
lower = np.zeros(num_vars)
upper = np.ones(num_vars) * 5.0

# Tell the helpers that indices [3, 4, 5] are integer variables.
_set_integer_split(3)

solution = construct_grasp(
    num_vars=num_vars,
    lower_arr=lower,
    upper_arr=upper,
    evaluator=sphere,
    initial_guess=None,
    alpha=0.2,           # 0 = pure greedy, 1 = pure random
    seed=42,
    num_candidates_per_step=12,
)
print("constructed:", solution, "cost:", sphere(solution))
```

---

### VND — Variable Neighborhood Descent (local search)

`local_search_vnd` improves a starting solution by cycling through flip,
swap, multiflip, group, and block neighbourhoods until no gain is found.

```python
import numpy as np
from givp.core.vnd import local_search_vnd
from givp.core.helpers import _set_integer_split

def sphere(x: np.ndarray) -> float:
    return float(np.sum(x ** 2))

_set_integer_split(3)  # first 3 indices are continuous, last 3 are integer

solution = np.array([2.5, 3.1, 0.8, 4.0, 2.0, 1.0])
lower    = np.zeros(6)
upper    = np.ones(6) * 5.0

improved = local_search_vnd(
    cost_fn=sphere,
    solution=solution,
    num_vars=6,
    max_iter=200,
    lower_arr=lower,
    upper_arr=upper,
)
print("before:", sphere(solution), "after:", sphere(improved))
```

Use `local_search_vnd_adaptive` to let the algorithm re-rank neighbourhoods
based on their hit-rate for the current problem:

```python
from givp.core.vnd import local_search_vnd_adaptive

improved = local_search_vnd_adaptive(
    cost_fn=sphere,
    solution=solution,
    num_vars=6,
    max_iter=200,
    lower_arr=lower,
    upper_arr=upper,
)
```

---

### ILS — Iterated Local Search (perturbation)

`ils_search` wraps VND inside a perturbation loop. It shakes the current
solution and re-applies VND, accepting an occasional worse result to escape
local optima.

```python
import numpy as np
from givp import GIVPConfig
from givp.core.ils import ils_search
from givp.core.helpers import _set_integer_split

def sphere(x: np.ndarray) -> float:
    return float(np.sum(x ** 2))

_set_integer_split(3)

config = GIVPConfig(
    ils_iterations=10,
    vnd_iterations=50,
    perturbation_strength=2,
)

solution = np.array([2.5, 3.1, 0.8, 4.0, 2.0, 1.0])
lower    = np.zeros(6)
upper    = np.ones(6) * 5.0

best_sol, best_cost = ils_search(
    solution=solution,
    current_cost=sphere(solution),
    num_vars=6,
    cost_fn=sphere,
    config=config,
    lower_arr=lower,
    upper_arr=upper,
)
print("ILS best cost:", best_cost)
```

---

### Path Relinking — intensification between elite solutions

`path_relinking` walks from a *source* to a *target* solution one coordinate
at a time, evaluating every intermediate point.  
`bidirectional_path_relinking` runs both directions and returns the global
best.

```python
import numpy as np
from givp.core.pr import path_relinking, bidirectional_path_relinking
from givp.core.helpers import _set_integer_split

def sphere(x: np.ndarray) -> float:
    return float(np.sum(x ** 2))

_set_integer_split(6)  # all variables treated as continuous for PR

source = np.array([4.0, 3.0, 2.0, 1.0, 0.5, 0.1])
target = np.array([0.1, 0.2, 0.3, 0.1, 0.0, 0.0])

# Forward walk from source towards target
best_sol, best_cost = path_relinking(
    cost_fn=sphere,
    source=source,
    target=target,
    strategy="best",   # "best" picks the locally optimal step;
    seed=0,
)
print("PR best cost:", best_cost)

# Bidirectional: explores source→target and target→source
best_sol, best_cost = bidirectional_path_relinking(
    cost_fn=sphere,
    sol1=source,
    sol2=target,
)
print("Bidirectional PR best cost:", best_cost)
```
