# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path
from typing import Dict, Iterable, Set


CoverageMap = Dict[str, Dict[int, int]]
ParserFn = Callable[[Path, Path], CoverageMap]


def _norm_path(path_text: str, workspace: Path) -> str:
    raw = path_text.replace("\\", "/")
    ws = workspace.as_posix().rstrip("/")
    if raw.startswith(ws + "/"):
        return raw[len(ws) + 1 :]

    if "/" in raw and workspace.name in raw:
        marker = "/" + workspace.name + "/"
        idx = raw.find(marker)
        if idx != -1:
            return raw[idx + len(marker) :]

    return raw.lstrip("./")


def _run_git_diff(base_sha: str, paths: list[str]) -> str:
    cmd = ["git", "diff", "--unified=0", f"{base_sha}...HEAD", "--", *paths]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"git diff failed with exit code {result.returncode}")
    return result.stdout


def _set_current_file(
    line: str,
    file_re: re.Pattern[str],
    workspace: Path,
    changed: Dict[str, Set[int]],
) -> tuple[bool, str | None]:
    file_match = file_re.match(line)
    if not file_match:
        return False, None

    path_text = file_match.group(1)
    if path_text == "/dev/null":
        return True, None

    current_file = _norm_path(path_text, workspace)
    changed.setdefault(current_file, set())
    return True, current_file


def _apply_hunk_line(line: str, hunk_re: re.Pattern[str], file_lines: Set[int]) -> None:
    hunk_match = hunk_re.match(line)
    if not hunk_match:
        return

    start = int(hunk_match.group(1))
    length = int(hunk_match.group(2) or "1")
    if length <= 0:
        return

    for line_no in range(start, start + length):
        file_lines.add(line_no)


def _parse_changed_lines(diff_text: str, workspace: Path) -> Dict[str, Set[int]]:
    changed: Dict[str, Set[int]] = {}
    current_file: str | None = None

    file_re = re.compile(r"^\+\+\+ b/(.+)$")
    hunk_re = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

    for line in diff_text.splitlines():
        is_file_line, next_file = _set_current_file(line, file_re, workspace, changed)
        if is_file_line:
            current_file = next_file
            continue

        if current_file is None:
            continue

        _apply_hunk_line(line, hunk_re, changed[current_file])

    return {k: v for k, v in changed.items() if v}


def _parse_lcov(report_path: Path, workspace: Path) -> CoverageMap:
    cov: CoverageMap = {}
    current_file: str | None = None

    with report_path.open("r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if line.startswith("SF:"):
                current_file = _norm_path(line[3:], workspace)
                cov.setdefault(current_file, {})
            elif line.startswith("DA:") and current_file is not None:
                body = line[3:]
                parts = body.split(",")
                if len(parts) >= 2:
                    line_no = int(parts[0])
                    hits = int(float(parts[1]))
                    cov[current_file][line_no] = hits
            elif line == "end_of_record":
                current_file = None

    return cov


def _parse_cobertura(report_path: Path, workspace: Path) -> CoverageMap:
    cov: CoverageMap = {}
    tree = ET.parse(report_path)
    root = tree.getroot()

    for class_node in root.findall(".//class"):
        filename = class_node.attrib.get("filename")
        if not filename:
            continue
        file_key = _norm_path(filename, workspace)
        file_cov = cov.setdefault(file_key, {})

        lines_parent = class_node.find("lines")
        if lines_parent is None:
            continue

        for line_node in lines_parent.findall("line"):
            num = line_node.attrib.get("number")
            hits = line_node.attrib.get("hits")
            if num is None or hits is None:
                continue
            file_cov[int(num)] = int(float(hits))

    return cov


def _select_parser(fmt: str) -> ParserFn:
    if fmt == "lcov":
        return _parse_lcov
    if fmt == "cobertura":
        return _parse_cobertura
    raise ValueError(f"Unsupported format: {fmt}")


def _sum_patch_coverage(
    changed: Dict[str, Set[int]],
    cov: CoverageMap,
    include_prefixes: Iterable[str],
) -> tuple[int, int, list[str]]:
    prefixes = tuple(p.rstrip("/") + "/" for p in include_prefixes)

    total = 0
    covered = 0
    missing_entries: list[str] = []

    for file_path, lines in changed.items():
        if not file_path.startswith(prefixes):
            continue

        file_cov = cov.get(file_path, {})
        for line_no in sorted(lines):
            total += 1
            hits = file_cov.get(line_no, 0)
            if hits > 0:
                covered += 1
            elif line_no not in file_cov:
                missing_entries.append(f"{file_path}:{line_no}")

    return total, covered, missing_entries


def main() -> int:
    parser = argparse.ArgumentParser(description="Check patch coverage against PR diff")
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--paths", required=True, help="Comma-separated include paths")
    parser.add_argument("--report-format", choices=["lcov", "cobertura"], required=True)
    parser.add_argument("--report-file", required=True)
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()

    workspace = Path.cwd().resolve()
    include_paths = [p.strip().strip("/") for p in args.paths.split(",") if p.strip()]

    if not include_paths:
        print("::error::No include paths provided")
        return 1

    diff_text = _run_git_diff(args.base_sha, include_paths)
    changed = _parse_changed_lines(diff_text, workspace)

    report_path = workspace / args.report_file
    if not report_path.exists():
        print(f"::error::{args.label}: coverage report not found: {args.report_file}")
        return 1

    parser_fn = _select_parser(args.report_format)
    cov = parser_fn(report_path, workspace)

    total, covered, missing = _sum_patch_coverage(changed, cov, include_paths)

    if total == 0:
        print(f"{args.label} patch coverage: N/A (no changed lines in {', '.join(include_paths)})")
        return 0

    pct = covered / total * 100.0
    print(f"{args.label} patch coverage: {pct:.1f}%  ({covered} / {total} changed lines)")

    if missing:
        preview = "\n".join(missing[:30])
        print("::warning::Changed lines not found in coverage report (counted as uncovered):")
        print(preview)
        if len(missing) > 30:
            print(f"... and {len(missing) - 30} more")

    if pct + 1e-9 < args.threshold:
        print(
            f"::error::{args.label} patch coverage below {args.threshold:.1f}% threshold "
            f"(got {pct:.1f}%)"
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
