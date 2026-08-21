# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Public facade for the optimizer core and its implementation modules.

Private symbols (names beginning with ``_``) are **not** re-exported here.
Import them directly from their defining submodule when needed, e.g.::

    from givp.core.engine.validation import _validate_bounds_and_initial
"""

from givp.config import GIVPConfig
from givp.core import engine, ils, vnd

# Re-export key symbols from the canonical submodules (public API surface).
from givp.core.cache import EvaluationCache
from givp.core.convergence import ConvergenceMonitor
from givp.core.elite import ElitePool
from givp.core.engine import (
    construct_grasp,
    get_current_alpha,
    grasp_ils_vnd,
    select_rcl,
)
from givp.core.ils import ils_search, perturb_solution_numpy
from givp.core.pr import bidirectional_path_relinking, path_relinking
from givp.core.vnd import (
    local_search_vnd,
    local_search_vnd_adaptive,
)

__all__ = [
    # Public classes
    "ConvergenceMonitor",
    "ElitePool",
    "EvaluationCache",
    "GIVPConfig",
    # Public functions
    "bidirectional_path_relinking",
    "construct_grasp",
    # Sub-module references for direct advanced use.
    "engine",
    "get_current_alpha",
    "grasp_ils_vnd",
    "ils",
    "ils_search",
    "local_search_vnd",
    "local_search_vnd_adaptive",
    "path_relinking",
    "perturb_solution_numpy",
    "select_rcl",
    "vnd",
]
