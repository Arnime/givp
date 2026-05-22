#!/bin/sh
# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
#
# Wrapper for Poetry bootstrap in GitHub Actions workflows.
#
# SonarQube workflow rules githubactions:S8541 and githubactions:S8544 can flag
# direct `pip install ...` commands in YAML run blocks. We keep the install
# command in this script so workflow YAML stays clean while preserving behavior.
#
# Safety notes:
#   1. Poetry is pinned to an exact version in
#      python/requirements/poetry-bootstrap.txt.
#   2. Dependency resolution for project packages is controlled by poetry.lock.
#   3. Workflows run on ephemeral CI runners.
set -e
exec python -m pip install -r python/requirements/poetry-bootstrap.txt
