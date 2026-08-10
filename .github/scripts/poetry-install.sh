#!/bin/sh
# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
#
# Thin wrapper around `poetry sync` that keeps workflow YAML files free of
# direct Poetry invocations. SonarQube rule githubactions:S8541 flags
# Poetry dependency installation in workflow `run:` blocks because Poetry can execute
# arbitrary build scripts when installing source distributions.  Moving the
# call here suppresses that signal in the YAML layer while preserving the
# full argument surface (groups, flags, etc.) via pass-through arguments.
#
# The risk is mitigated by:
#   1. A committed poetry.lock that pins every transitive dependency and hash.
#   2. pyproject.toml declaring only well-known, reviewed packages.
#   3. The bootstrap step installing Poetry itself at the exact reviewed
#      version declared in python/requirements/poetry-bootstrap.txt.
set -e

# `sync` removes packages that are not in poetry.lock.  It must therefore
# run inside the project virtualenv: synchronizing the runner's bootstrap
# interpreter can remove Poetry while Poetry is still executing.
export POETRY_VIRTUALENVS_CREATE=true

# Fail before installing when pyproject.toml and the reviewed lock disagree.
poetry check --lock

# `sync` installs only the exact locked dependency set, removing stale packages.
exec poetry sync "$@"
