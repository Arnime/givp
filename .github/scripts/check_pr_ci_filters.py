#!/usr/bin/env python3
"""Check selective CI gates and always-reported language coverage checks."""

import re
from pathlib import Path

RELEASE_PROVENANCE_WORKFLOWS = ".github/workflows/release-provenance.yml"
RELEASE_PYTHON_WORKFLOWS = ".github/workflows/release-python.yml"
RELEASE_CPP_WORKFLOWS = ".github/workflows/release-cpp.yml"
NEEDS_CONTEXT = "needs: context"
NEEDS_CONTEXT_AND_PROVENANCE = "needs: [context, provenance]"

ROOT = Path(__file__).resolve().parents[2]
EXPECTATIONS = {
    ".github/workflows/ci-python.yml": (
        "python/src",
        "python/pyproject.toml",
        "source_changed",
    ),
    ".github/workflows/ci-rust.yml": ("rust/src", "rust/Cargo.toml", "source_changed"),
    ".github/workflows/ci-julia.yml": (
        "julia/src",
        "julia/Project.toml",
        "source_changed",
    ),
    ".github/workflows/ci-r.yml": ("r/R", "r/DESCRIPTION", "source_changed"),
    ".github/workflows/ci-cpp.yml": (
        "cpp/include",
        "cpp/CMakeLists.txt",
        "source_changed",
    ),
    ".github/workflows/codeql.yml": ("python/src/**", "python/poetry.lock"),
    ".github/workflows/security.yml": ("python/src/**", "python/poetry.lock"),
}
ALWAYS_REPORTED_COVERAGE = {
    ".github/workflows/ci-python.yml": "Coverage not required for this pull request",
    ".github/workflows/ci-rust.yml": "name: coverage-rust",
    ".github/workflows/ci-julia.yml": "name: coverage-julia",
    ".github/workflows/ci-r.yml": "name: coverage-r",
    ".github/workflows/ci-cpp.yml": "name: coverage-cpp",
}
SLSA_WORKFLOWS = (
    RELEASE_PROVENANCE_WORKFLOWS,
    ".github/workflows/backfill-provenance.yml",
)
REUSABLE_RELEASE_WORKFLOWS = (
    ".github/workflows/release-context.yml",
    RELEASE_PYTHON_WORKFLOWS,
    RELEASE_CPP_WORKFLOWS,
    ".github/workflows/release-r.yml",
    RELEASE_PROVENANCE_WORKFLOWS,
    ".github/workflows/publish-rust.yml",
    ".github/workflows/register-julia.yml",
    ".github/workflows/verify-r-universe.yml",
)


def _read(relative_path: str) -> str:
    """Read one repository file used by the CI contract checks."""
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _check_expected_snippets() -> list[str]:
    """Return errors for missing language and security workflow markers."""
    errors: list[str] = []
    for relative_path, snippets in EXPECTATIONS.items():
        content = _read(relative_path)
        errors.extend(
            f"{relative_path}: missing {snippet!r}"
            for snippet in snippets
            if snippet not in content
        )
    return errors


def _check_coverage_contracts() -> list[str]:
    """Return errors when required coverage jobs can be skipped entirely."""
    errors: list[str] = []
    for relative_path, required_name in ALWAYS_REPORTED_COVERAGE.items():
        content = _read(relative_path)
        if "  pull_request:\n    paths:" in content:
            errors.append(f"{relative_path}: coverage must run on every PR")
        if required_name not in content:
            errors.append(f"{relative_path}: missing always-reported coverage check")
    return errors


def _check_codeql_pins() -> list[str]:
    """Return errors for missing or inconsistent immutable CodeQL pins."""
    codeql_pins = dict(
        re.findall(
            r"github/codeql-action/(init|analyze)@([0-9a-f]{40})",
            _read(".github/workflows/codeql.yml"),
        )
    )
    if set(codeql_pins) != {"init", "analyze"}:
        return [".github/workflows/codeql.yml: missing immutable init/analyze pins"]
    if len(set(codeql_pins.values())) != 1:
        return [".github/workflows/codeql.yml: init and analyze must use the same pin"]
    return []


def _check_slsa_pins() -> list[str]:
    """Return errors for absent or inconsistent SLSA generator pins."""
    errors: list[str] = []
    pins: list[str] = []
    pattern = (
        r"slsa-framework/slsa-github-generator/"
        r"\.github/workflows/generator_generic_slsa3\.yml@([0-9a-f]{40})"
    )
    for relative_path in SLSA_WORKFLOWS:
        content = _read(relative_path)
        match = re.search(pattern, content)
        if match is None:
            errors.append(f"{relative_path}: missing immutable SLSA generator pin")
        else:
            pins.append(match.group(1))
        if "compile-generator: true" not in content:
            errors.append(
                f"{relative_path}: SHA-pinned SLSA workflows must compile the generator"
            )
        if "FORCE_JAVASCRIPT_ACTIONS_TO_NODE24" in content:
            errors.append(
                f"{relative_path}: SLSA v2.1.0 actions must not be forced to Node.js 24"
            )
    if len(pins) == len(SLSA_WORKFLOWS) and len(set(pins)) != 1:
        errors.append(
            "SLSA generator pins must match in Release and Backfill Provenance"
        )
    return errors


def _missing_release_snippets(
    content: str, snippets: tuple[str, ...], message: str
) -> list[str]:
    """Return one formatted error for every absent release contract snippet."""
    return [
        message.format(snippet=snippet)
        for snippet in snippets
        if snippet not in content
    ]


def _release_job_block(content: str, job_name: str) -> str:
    """Return one top-level release job block, or an empty string if absent."""
    marker = f"  {job_name}:\n"
    start = content.find(marker)
    if start < 0:
        return ""
    following_job = content.find("\n  ", start + len(marker))
    while following_job >= 0:
        next_line = content[following_job + 1 :].splitlines()[0]
        if next_line.endswith(":") and not next_line.startswith("    "):
            return content[start:following_job]
        following_job = content.find("\n  ", following_job + 1)
    return content[start:]


def _check_python_release() -> list[str]:
    """Return errors when Python releases lose historical-layout support."""
    relative_path = RELEASE_PYTHON_WORKFLOWS
    content = _read(relative_path)
    errors: list[str] = []
    if "uses: ./.github/actions/setup-poetry" in content:
        errors.append(
            f"{relative_path}: historical tags cannot use the local Poetry action"
        )
    errors.extend(
        _missing_release_snippets(
            content,
            (
                "snok/install-poetry@a783c322200f0519c7926aa6faa857c4e23e9263",
                "[ -f python/pyproject.toml ]",
                "elif [ -f pyproject.toml ]",
                "mv dist python/dist",
            ),
            f"{relative_path}: missing historical Python layout support {{snippet!r}}",
        )
    )
    return errors


def _check_release_orchestrator() -> list[str]:
    """Return errors when the central release stops being a pure orchestrator."""
    relative_path = ".github/workflows/release.yml"
    content = _read(relative_path)
    job_contracts = {
        "context": ("release-context.yml", None),
        "python": ("release-python.yml", NEEDS_CONTEXT),
        "cpp": ("release-cpp.yml", NEEDS_CONTEXT),
        "r": ("release-r.yml", NEEDS_CONTEXT),
        "provenance": ("release-provenance.yml", "needs: [context, python, cpp, r]"),
        "publish-rust": ("publish-rust.yml", NEEDS_CONTEXT_AND_PROVENANCE),
        "register-julia": ("register-julia.yml", NEEDS_CONTEXT_AND_PROVENANCE),
        "sync-cpp-registries": (
            "sync-cpp-registries.yml",
            NEEDS_CONTEXT_AND_PROVENANCE,
        ),
        "verify-r-universe": ("verify-r-universe.yml", "needs: [context, r]"),
    }
    errors: list[str] = []
    for job_name, (workflow_name, dependency) in job_contracts.items():
        block = _release_job_block(content, job_name)
        required = [f"uses: ./.github/workflows/{workflow_name}"]
        if dependency is not None:
            required.append(dependency)
        errors.extend(
            _missing_release_snippets(
                block,
                tuple(required),
                f"{relative_path}: job {job_name!r} misses {{snippet!r}}",
            )
        )
    forbidden = (
        "actions/checkout@",
        "slsa-framework/slsa-github-generator",
        "cargo publish",
        "R CMD build",
        "python -m build",
    )
    errors.extend(
        f"{relative_path}: orchestrator contains implementation detail {snippet!r}"
        for snippet in forbidden
        if snippet in content
    )
    if len(content.splitlines()) > 120:
        errors.append(f"{relative_path}: orchestrator exceeds 120 lines")
    return errors


def _check_release_context() -> list[str]:
    """Return errors when tag validation can no longer fail before checkout."""
    relative_path = ".github/workflows/release-context.yml"
    content = _read(relative_path)
    errors = _missing_release_snippets(
        content,
        (
            "Expected a vX.Y.Z semantic-version tag",
            'gh api "repos/${GH_REPO}/git/ref/tags/${TAG}"',
            'echo "tag=$TAG" >> "$GITHUB_OUTPUT"',
            'echo "version=$VERSION" >> "$GITHUB_OUTPUT"',
        ),
        f"{relative_path}: missing pre-checkout tag contract {{snippet!r}}",
    )
    if "actions/checkout@" in content:
        errors.append(f"{relative_path}: tag validation must run before checkout")
    return errors


def _check_release_reusability() -> list[str]:
    """Return errors when specialized release workflows gain manual triggers."""
    errors: list[str] = []
    for workflow_path in REUSABLE_RELEASE_WORKFLOWS:
        content = _read(workflow_path)
        if "  workflow_call:" not in content:
            errors.append(f"{workflow_path}: missing workflow_call trigger")
        if "  workflow_dispatch:" in content:
            errors.append(f"{workflow_path}: reusable releases cannot be manual")
    if "workflow_dispatch" in _read(".github/workflows/sync-cpp-registries.yml"):
        errors.append(
            "sync-cpp-registries.yml: release synchronization cannot be manual"
        )
    return errors


def _check_release_artifacts() -> list[str]:
    """Return errors when canonical release artifact names drift."""
    contracts = {
        RELEASE_PYTHON_WORKFLOWS: "python-release-artifacts",
        ".github/workflows/release-r.yml": "r-release-artifacts",
        RELEASE_CPP_WORKFLOWS: "cpp-release-artifacts-${VERSION}",
    }
    return [
        f"{workflow_path}: missing canonical artifact name {artifact_name!r}"
        for workflow_path, artifact_name in contracts.items()
        if artifact_name not in _read(workflow_path)
    ]


def _check_release_services() -> list[str]:
    """Return errors when external release checks lose safe behavior."""
    r_universe = _read(".github/workflows/verify-r-universe.yml")
    errors = _missing_release_snippets(
        r_universe,
        ("json.load(sys.stdin)", "::warning::R-universe did not show"),
        "verify-r-universe.yml: missing non-blocking JSON check {snippet!r}",
    )
    errors.extend(
        _missing_release_snippets(
            _read(RELEASE_PROVENANCE_WORKFLOWS),
            (
                "GH_REPO: ${{ github.repository }}",
                'gh release view "$TAG" --repo "$GH_REPO"',
            ),
            "release-provenance.yml: missing repository-safe asset check {snippet!r}",
        )
    )
    release = _read(".github/workflows/release.yml")
    publish_python = _release_job_block(release, "publish-python")
    errors.extend(
        _missing_release_snippets(
            publish_python,
            (
                "needs: [provenance, python]",
                "environment:",
                "name: pypi",
                "id-token: write",
                "pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33",
            ),
            "release.yml: inline PyPI publication misses {snippet!r}",
        )
    )
    if "uses: ./.github/workflows/publish-python.yml" in release:
        errors.append("release.yml: PyPI trusted publishing cannot use a reusable workflow")
    sync_cpp = _read(".github/workflows/sync-cpp-registries.yml")
    if "REGISTRY_FORK_TOKEN:\n        required: true" in sync_cpp:
        errors.append(
            "sync-cpp-registries.yml: environment secret cannot be a required call secret"
        )
    errors.extend(
        _missing_release_snippets(
            sync_cpp,
            (
                "ref: ${{ github.sha }}",
                'SOURCE_REF="$GITHUB_SHA"',
                'if [[ -z "$INPUT_TAG" ]]; then',
            ),
            "sync-cpp-registries.yml: missing branch-safe release contract "
            "{snippet!r}",
        )
    )
    if "format('refs/tags/{0}', inputs.tag)" in sync_cpp:
        errors.append(
            "sync-cpp-registries.yml: automation must not be checked out from "
            "historical release tags"
        )
    secret_contracts = (
        (
            _read(".github/workflows/publish-rust.yml"),
            _release_job_block(release, "publish-rust"),
            "CARGO_REGISTRY_TOKEN",
        ),
        (
            sync_cpp,
            _release_job_block(release, "sync-cpp-registries"),
            "REGISTRY_FORK_TOKEN",
        ),
    )
    for workflow, caller, secret_name in secret_contracts:
        errors.extend(
            _missing_release_snippets(
                workflow,
                (f"{secret_name}:", "required: false"),
                f"reusable release secret {secret_name!r} misses {{snippet!r}}",
            )
        )
        expected_forwarding = f"{secret_name}: ${{{{ secrets.{secret_name} }}}}"
        if expected_forwarding not in caller:
            errors.append(f"release.yml: {secret_name} is not explicitly forwarded")
        if "secrets: inherit" in caller:
            errors.append(f"release.yml: {secret_name} must not expose unrelated secrets")
    return errors


def _check_cpp_release() -> list[str]:
    """Return errors when C++ releases lose cross-platform or legacy support."""
    content = _read(RELEASE_CPP_WORKFLOWS)
    errors: list[str] = []
    forbidden = {
        "python .github/scripts/validate_unified_version.py": (
            "release-cpp.yml: historical tags cannot use current local scripts"
        ),
        "--target RUN_TESTS": (
            "release-cpp.yml: use cross-platform ctest instead of RUN_TESTS"
        ),
        "--build-config Release \\": (
            "release-cpp.yml: PowerShell steps cannot use Bash line continuations"
        ),
    }
    errors.extend(
        message for snippet, message in forbidden.items() if snippet in content
    )
    errors.extend(
        _missing_release_snippets(
            content,
            (
                'Path("cpp/CMakeLists.txt")',
                "ctest --test-dir cpp/build/release-test --build-config Release",
                'CHANGELOG_PATH="docs/project/changelog.md"',
                'CHANGELOG_PATH="CHANGELOG.md"',
            ),
            "release-cpp.yml: missing historical layout support {snippet!r}",
        )
    )
    return errors


def main() -> None:
    """Fail when CI loses its selective validation or required-check contract."""
    checks = (
        _check_expected_snippets,
        _check_coverage_contracts,
        _check_codeql_pins,
        _check_slsa_pins,
        _check_python_release,
        _check_release_orchestrator,
        _check_release_context,
        _check_release_reusability,
        _check_release_artifacts,
        _check_release_services,
        _check_cpp_release,
    )
    missing = [error for check in checks for error in check()]
    if missing:
        raise SystemExit("\n".join(missing))
    print("PR CI path-filter checks passed.")


if __name__ == "__main__":
    main()
