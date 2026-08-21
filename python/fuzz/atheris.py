# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Linux coverage-guided fuzz target powered by Atheris."""

from __future__ import annotations

import platform
import sys
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from typing import cast

from fuzz.target import fuzz_bytes

FuzzTarget = Callable[[bytes], None]


@dataclass(frozen=True)
class AtherisBackend:
    """Typed subset of the platform-specific Atheris API."""

    instrument: Callable[[FuzzTarget], FuzzTarget]
    setup: Callable[[list[str], FuzzTarget], None]
    run: Callable[[], None]


def _load_backend() -> AtherisBackend:
    """Load Atheris on Linux without making it a Windows import dependency."""
    if platform.system() != "Linux":
        raise RuntimeError(
            "Atheris is available only on Linux; run `python -m fuzz` "
            "for the cross-platform Hypothesis target"
        )
    module = import_module("atheris")
    api = vars(module)
    return AtherisBackend(
        instrument=cast(
            Callable[[FuzzTarget], FuzzTarget], api["instrument_func"]
        ),
        setup=cast(
            Callable[[list[str], FuzzTarget], None], api["Setup"]
        ),
        run=cast(Callable[[], None], api["Fuzz"]),
    )


def fuzz(data: bytes) -> None:
    """Drive GIVP with arbitrary bytes supplied by Atheris."""
    fuzz_bytes(data)


def main() -> None:
    """Configure and start Atheris."""
    backend = _load_backend()
    target = backend.instrument(fuzz)
    backend.setup(sys.argv, target)
    backend.run()


if __name__ == "__main__":
    main()
