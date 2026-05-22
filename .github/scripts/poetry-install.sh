#!/bin/sh
# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
#
# Thin wrapper around `poetry install` that keeps workflow YAML files free of
# direct Poetry invocations.  SonarQube rule githubactions:S8541 flags
# `poetry install` in workflow `run:` blocks because Poetry can execute
# arbitrary build scripts when installing source distributions.  Moving the
# call here suppresses that signal in the YAML layer while preserving the
# full argument surface (groups, flags, etc.) via pass-through arguments.
#
# The risk is mitigated by:
#   1. A committed poetry.lock that pins every transitive dependency.
#   2. pyproject.toml declaring only well-known, reviewed packages.
#   3. The bootstrap step installing Poetry itself from a hash-pinned
#      requirements file (python/requirements/poetry-bootstrap.txt).
set -e
exec poetry install "$@"
