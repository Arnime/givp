# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
"""Public facade for the Python GIVP fuzz targets."""

from fuzz.target import fuzz_bytes, run_case

__all__ = ["fuzz_bytes", "run_case"]
