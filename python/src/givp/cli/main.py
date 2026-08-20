# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Executable entry point for the GIVP command line."""

from __future__ import annotations

import sys

from givp.cli.parser import _build_parser


def main() -> None:
    """Parse command-line arguments and execute the selected command."""
    namespace = _build_parser().parse_args()
    sys.exit(namespace.func(namespace))
