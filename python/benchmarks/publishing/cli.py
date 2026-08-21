# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Command-line interface for documentation publishing."""

from __future__ import annotations

import argparse
from pathlib import Path

from benchmarks.publishing.normalization import load_artifact, parse_artifact_specs
from benchmarks.publishing.pages import build_index, write_report_page

DEFAULT_REPO_URL_BASE = "https://github.com/Arnime/givp/blob/main"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for benchmark artifact publication."""

    parser = argparse.ArgumentParser(
        prog="python -m benchmarks.publishing",
        description="Publish benchmark artifact pages under docs/examples/.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        required=True,
        help="Explicit repository root used to resolve artifact paths.",
    )
    parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        metavar="LABEL=PATH",
        help="Override one or more input artifacts. Can be passed multiple times.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory that will receive the generated Markdown and SVG files.",
    )
    parser.add_argument(
        "--repo-url-base",
        default=DEFAULT_REPO_URL_BASE,
        help="Base GitHub blob URL used for source links inside generated pages.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Generate all benchmark report pages and return a process exit code."""

    args = parse_args(argv)
    try:
        specs = parse_artifact_specs(args.artifact, args.repo_root)
        reports = [
            load_artifact(label, path, args.repo_root) for label, path in specs
        ]
    except (OSError, ValueError) as exc:
        print(f"[error] {exc}")
        return 1

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir.joinpath("index.md").write_text(
        build_index(reports, args.repo_url_base),
        encoding="utf-8",
    )
    for report in reports:
        write_report_page(report, output_dir, args.repo_url_base)

    print(f"Generated {len(reports)} benchmark report pages in {output_dir}")
    return 0
