"""Public Variable Neighborhood Descent facade."""

from givp.core.vnd.adaptive import local_search_vnd_adaptive
from givp.core.vnd.standard import local_search_vnd

__all__ = [
    "local_search_vnd",
    "local_search_vnd_adaptive",
]
