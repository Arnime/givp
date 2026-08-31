"""Build and validate derived deterministic artifacts from a worker response.

This script never edits the frozen benchmark.  It receives all input and output
paths explicitly so each language client can write its validation under the
ignored experiment output directory.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from givp.examples.synthetic_hydropower.benchmark.deterministic.interop import (
    build_batch_request,
    compare_interop_artifacts,
    write_interop_artifacts,
)
from givp.examples.synthetic_hydropower.interop import canonical_cascade_config


def parse_arguments() -> argparse.Namespace:
    """Parse explicitly supplied deterministic protocol paths."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inflows", type=Path, required=True)
    parser.add_argument("--schedules", type=Path, required=True)
    parser.add_argument("--response", type=Path, required=False)
    parser.add_argument("--request-output", type=Path, required=False)
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--decimal-places", type=int, default=6)
    parser.add_argument("--tolerance", type=float, default=1e-6)
    return parser.parse_args()


def main() -> None:
    """Generate a batch request or validate a response against frozen tables."""
    args = parse_arguments()
    if (args.response is None) == (args.request_output is None):
        raise ValueError("supply exactly one of --response or --request-output")
    inflows = pd.read_csv(args.inflows)
    schedules = pd.read_csv(args.schedules)
    if args.request_output is not None:
        request = build_batch_request(
            inflows, schedules, canonical_cascade_config().periods
        )
        args.request_output.parent.mkdir(parents=True, exist_ok=True)
        args.request_output.write_text(
            json.dumps(request, allow_nan=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {len(request['requests'])} deterministic requests")
        return

    response = json.loads(args.response.read_text(encoding="utf-8"))
    artifacts = write_interop_artifacts(
        response,
        args.inflows,
        args.schedules,
        canonical_cascade_config(),
        args.output_dir,
        args.decimal_places,
    )
    report = compare_interop_artifacts(artifacts, args.reference_dir, args.tolerance)
    report_path = args.output_dir / "validation.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not all(item["passed"] for item in report.values()):
        raise RuntimeError(f"deterministic interoperability validation failed: {report}")
    print(f"validated {sum(item['rows'] for item in report.values())} rows")


if __name__ == "__main__":
    main()
