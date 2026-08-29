"""Persistent Python client for the synthetic hydropower JSON Lines worker."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Mapping

import numpy as np
from givp.examples.synthetic_hydropower.optimization import (
    OptimizationDefinition,
    make_optimization_request,
)
from numpy.typing import NDArray


class HydropowerWorker:
    """Own one reference worker for all objective evaluations of one GIVP run."""

    def __init__(self) -> None:
        """Start the unbuffered Python worker with bidirectional pipes."""
        self._process = subprocess.Popen[
            str
        ](
            [
                sys.executable,
                "-u",
                "-m",
                "givp.examples.synthetic_hydropower.cli",
                "worker",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

    def evaluate(
        self,
        vector: NDArray[np.float64],
        definition: OptimizationDefinition,
        *,
        case_id: str,
    ) -> dict[str, object]:
        """Evaluate a projected vector and return its single physical result."""
        if self._process.stdin is None or self._process.stdout is None:
            raise RuntimeError("hydropower worker pipes are unavailable")
        request = make_optimization_request(vector, definition, case_id)
        self._process.stdin.write(json.dumps(request, allow_nan=False) + "\n")
        self._process.stdin.flush()
        line = self._process.stdout.readline()
        if not line:
            details = self._read_error()
            raise RuntimeError(f"hydropower worker stopped before a response: {details}")
        response: object = json.loads(line)
        if not isinstance(response, Mapping):
            raise TypeError("hydropower worker returned a non-object response")
        if "error" in response:
            raise RuntimeError(f"hydropower worker rejected the request: {response['error']}")
        results = response.get("results")
        if not isinstance(results, list) or len(results) != 1 or not isinstance(results[0], dict):
            raise RuntimeError("hydropower worker returned no single result")
        return results[0]

    def close(self) -> None:
        """Terminate the child process without leaving a background worker."""
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)

    def _read_error(self) -> str:
        if self._process.stderr is None:
            return "stderr unavailable"
        return self._process.stderr.read().strip() or "no stderr output"
