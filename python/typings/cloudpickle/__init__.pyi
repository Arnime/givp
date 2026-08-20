"""Type declarations for the cloudpickle API used by GIVP."""

# Stub parameters declare the external API and have no executable body.
# pylint: disable=missing-function-docstring,unused-argument

from collections.abc import Callable
from typing import Any

def dumps(obj: object, protocol: int | None = ...) -> bytes: ...
def loads(data: bytes) -> Callable[..., Any]: ...
