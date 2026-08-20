# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Argument-parser construction for the GIVP command line."""

from __future__ import annotations

import argparse

from givp.cli.commands import _cmd_run


def _build_parser() -> argparse.ArgumentParser:
    """Build the root parser and its supported subcommands."""
    parser = argparse.ArgumentParser(
        prog="givp",
        description="GRASP-ILS-VND-PR optimizer CLI",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    subparsers.required = True

    run_parser = subparsers.add_parser(
        "run", help="Run the optimizer on an objective function"
    )
    run_parser.add_argument("--func-file", metavar="PATH")
    run_parser.add_argument("--func-name", metavar="NAME")
    run_parser.add_argument("--bounds", metavar="JSON")
    run_parser.add_argument(
        "--direction", choices=["minimize", "maximize"], default=None
    )
    run_parser.add_argument("--config", metavar="JSON", default=None)
    run_parser.add_argument("--seed", type=int, default=None)
    run_parser.add_argument("--json", dest="json_input", metavar="JSON|-", default=None)
    run_parser.set_defaults(func=_cmd_run)
    return parser
