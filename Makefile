# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT
#
# Makefile for GIVP quality gates: lint, format, typecheck across all languages.
# Usage: make cpp-all  |  make python-all  |  make quality-all
#
# C++ targets require WSL or Linux with clang-format, clang-tidy, cmake, ctest, lcov.
# Other targets are OS-agnostic.

.PHONY: help

help:
	@echo "GIVP Quality Gate Makefile"
	@echo "=========================="
	@echo ""
	@echo "C++ (WSL/Linux):"
	@echo "  make cpp-format-check    Check clang-format (dry-run, no modifications)"
	@echo "  make cpp-lint            Run clang-tidy static analysis"
	@echo "  make cpp-build           Configure and build with CMake (Release mode)"
	@echo "  make cpp-test            Run C++ unit tests via ctest"
	@echo "  make cpp-coverage        Run C++ coverage gate with lcov (>=90%)"
	@echo "  make cpp-all             Run format-check, lint, build, test, coverage in sequence"
	@echo ""
	@echo "Python:"
	@echo "  make python-lint         Run ruff linter on src/tests"
	@echo "  make python-format-check Check ruff formatter (no modifications)"
	@echo "  make python-typecheck    Run mypy strict type checking"
	@echo "  make python-coverage     Run pytest coverage gate (>=95%)"
	@echo "  make python-all          Run lint, format-check, typecheck, coverage in sequence"
	@echo ""
	@echo "Julia:"
	@echo "  make julia-test          Run Julia tests with Pkg.test()"
	@echo "  make julia-format-check  Check JuliaFormatter (dry-run, no modifications)"
	@echo "  make julia-lint          Run Aqua.jl and JET.jl checks"
	@echo "  make julia-coverage      Run Julia coverage gate with CoverageTools (>=95%)"
	@echo "  make julia-all           Run test, format-check, lint, coverage in sequence"
	@echo ""
	@echo "Rust:"
	@echo "  make rust-lint           Run cargo clippy with -D warnings"
	@echo "  make rust-format-check   Check cargo fmt (dry-run, no modifications)"
	@echo "  make rust-test           Run cargo test"
	@echo "  make rust-coverage       Run cargo llvm-cov coverage gate (>=90%)"
	@echo "  make rust-all            Run format-check, lint, test, coverage in sequence"
	@echo ""
	@echo "R:"
	@echo "  make r-lint              Run lintr::lint_package"
	@echo "  make r-format-check      Check R code formatting (dry-run, no modifications)"
	@echo "  make r-coverage          Run covr coverage gate (>=90%)"
	@echo "  make r-all               Run lint, format-check, coverage in sequence"
	@echo ""
	@echo "Combined:"
	@echo "  make quality-all         Run all quality gates for all languages"
	@echo "  make local-ci            Run docker-compose local-ci (equiv. bash scripts/local-ci/run.sh)"

# ──────────────────────────────────────────────────────────────────────────────
# C++ (WSL/Linux only)
# ──────────────────────────────────────────────────────────────────────────────

CPP_SRC_DIR := cpp/include
CPP_TESTS_DIR := cpp/tests
CPP_BENCH_DIR := cpp/benchmarks
BUILD_DIR := build
BUILD_TIDY_DIR := build_tidy
BUILD_COV_DIR := build_cov

.PHONY: cpp-format-check cpp-lint cpp-build cpp-test cpp-coverage cpp-all cpp-clean

cpp-format-check:
	@echo "[C++] Checking clang-format (dry-run)..."
	@{ \
		find $(CPP_SRC_DIR) -type f \( -name '*.hpp' -o -name '*.h' \) -print0; \
		find $(CPP_TESTS_DIR) -type f \( -name '*.cpp' -o -name '*.hpp' -o -name '*.h' \) -print0; \
		find $(CPP_BENCH_DIR) -type f \( -name '*.cpp' -o -name '*.hpp' -o -name '*.h' \) -print0; \
	} | xargs -0 -r clang-format --dry-run --Werror
	@echo "[C++] ✓ clang-format check passed"

cpp-lint:
	@echo "[C++] Running clang-tidy static analysis..."
	@cmake -S cpp -B $(BUILD_TIDY_DIR) \
		-DCMAKE_C_COMPILER=clang \
		-DCMAKE_CXX_COMPILER=clang++ \
		-DGIVP_BUILD_TESTS=ON \
		-DGIVP_BUILD_BENCHMARKS=ON \
		-DCMAKE_EXPORT_COMPILE_COMMANDS=ON
	@find cpp/tests cpp/benchmarks -type f -name '*.cpp' -print0 \
		| xargs -0 -r -n 1 clang-tidy -p $(BUILD_TIDY_DIR) \
			--header-filter='cpp/include/.*' \
			--warnings-as-errors='*'
	@echo "[C++] ✓ clang-tidy analysis passed"

cpp-build:
	@echo "[C++] Building with CMake (Release)..."
	@cmake -S cpp -B $(BUILD_DIR) -DCMAKE_BUILD_TYPE=Release \
		-DGIVP_BUILD_TESTS=ON -DGIVP_BUILD_BENCHMARKS=OFF
	@cmake --build $(BUILD_DIR) --parallel
	@echo "[C++] ✓ Build succeeded"

cpp-test: cpp-build
	@echo "[C++] Running unit tests..."
	@ctest --test-dir $(BUILD_DIR) --output-on-failure
	@echo "[C++] ✓ All tests passed"

cpp-coverage:
	@echo "[C++] Running coverage gate (>=90%)..."
	@cmake -S cpp -B $(BUILD_COV_DIR) -DCMAKE_BUILD_TYPE=Debug \
		-DCMAKE_CXX_FLAGS="--coverage" -DCMAKE_EXE_LINKER_FLAGS="--coverage" \
		-DGIVP_BUILD_TESTS=ON -DGIVP_BUILD_BENCHMARKS=OFF
	@cmake --build $(BUILD_COV_DIR) --parallel
	@ctest --test-dir $(BUILD_COV_DIR) --output-on-failure
	@lcov --capture \
		--directory $(BUILD_COV_DIR) \
		--output-file coverage_raw.info \
		--gcov-tool gcov \
		--ignore-errors source,gcov,negative \
		--rc geninfo_unexecuted_blocks=1
	@lcov --remove coverage_raw.info \
		"*/$(BUILD_COV_DIR)/_deps/*" \
		'/usr/*' \
		--output-file coverage.info \
		--ignore-errors source,negative
	@lcov --list coverage.info
	@hit=$$(grep '^LH:' coverage.info | awk -F: '{s+=$$2} END {print s+0}'); \
	 total=$$(grep '^LF:' coverage.info | awk -F: '{s+=$$2} END {print s+0}'); \
	 if [ "$$total" -eq 0 ]; then \
	 	echo "[C++] No coverage data found in coverage.info"; \
	 	exit 1; \
	 fi; \
	 pct=$$(awk "BEGIN {printf \"%.1f\", $$hit / $$total * 100}"); \
	 echo "[C++] Coverage: $${pct}% ($$hit / $$total lines)"; \
	 awk "BEGIN { if ($$hit / $$total * 100 < 90.0) { print \"[C++] Coverage below 90% threshold (got $${pct}%)\"; exit 1 } }"
	@echo "[C++] ✓ Coverage gate passed"

cpp-clean:
	@rm -rf $(BUILD_DIR) $(BUILD_TIDY_DIR) $(BUILD_COV_DIR)
	@echo "[C++] ✓ Cleaned build directories"

cpp-all: cpp-format-check cpp-lint cpp-build cpp-test cpp-coverage
	@echo "[C++] ✓✓✓ All quality gates passed"

# ──────────────────────────────────────────────────────────────────────────────
# Python
# ──────────────────────────────────────────────────────────────────────────────

PY_SRC := python/src
PY_TESTS := python/tests
POETRY ?= poetry

.PHONY: python-lint python-lint-fix python-format-check python-format-fix python-fix python-typecheck python-coverage python-all

python-lint:
	@echo "[Python] Running ruff linter..."
	$(POETRY) run ruff check $(PY_SRC) $(PY_TESTS)
	@echo "[Python] ✓ ruff linter passed"


python-lint-fix:
	@echo "[Python] Fixing ruff lint issues (auto-fix)..."
	$(POETRY) run ruff check --fix $(PY_SRC) $(PY_TESTS)
	@echo "[Python] ✓ ruff lint auto-fix done"

python-format-check:
	@echo "[Python] Checking ruff formatter (dry-run)..."
	$(POETRY) run ruff format --check $(PY_SRC) $(PY_TESTS)
	@echo "[Python] ✓ ruff format check passed"


python-format-fix:
	@echo "[Python] Applying ruff formatter..."
	$(POETRY) run ruff format $(PY_SRC) $(PY_TESTS)
	@echo "[Python] ✓ ruff format applied"

python-fix: python-lint-fix python-format-fix
	@echo "[Python] ✓ All auto-fixes applied (run make python-all to verify)"

python-typecheck:
	@echo "[Python] Running mypy strict type checking..."
	$(POETRY) run mypy
	@echo "[Python] ✓ mypy typecheck passed"

python-coverage:
	@echo "[Python] Running pytest coverage gate (>=95%)..."
	$(POETRY) run pytest --cov=givp --cov-report=xml:coverage-python.xml --cov-fail-under=95
	@echo "[Python] ✓ Coverage gate passed"

python-all: python-lint python-format-check python-typecheck python-coverage
	@echo "[Python] ✓✓✓ All quality gates passed"

# ──────────────────────────────────────────────────────────────────────────────
# Julia
# ──────────────────────────────────────────────────────────────────────────────

JULIA_PROJECT := julia

.PHONY: julia-test julia-format-check julia-lint julia-coverage julia-all

julia-test:
	@echo "[Julia] Running tests..."
	julia --project=$(JULIA_PROJECT) -e 'using Pkg; Pkg.test()'
	@echo "[Julia] ✓ Julia tests passed"

julia-format-check:
	@echo "[Julia] Checking JuliaFormatter (dry-run)..."
	julia -e '\
		using Pkg; \
		Pkg.activate(; temp=true); \
		Pkg.add("JuliaFormatter"); \
		using JuliaFormatter; \
		bad_files = []; \
		for f in walkdir("julia/src"); \
			f[1] == "julia/src" && continue; \
			for fname in filter(x -> endswith(x, ".jl"), f[3]); \
				fpath = joinpath(f[1], fname); \
				orig = read(fpath, String); \
				fmt = format_text(orig); \
				if orig != fmt; \
					push!(bad_files, fpath); \
				end; \
			end; \
		end; \
		if !isempty(bad_files); \
			println("Unformatted files:"); \
			foreach(println, bad_files); \
			exit(1); \
		end'
	@echo "[Julia] ✓ JuliaFormatter check passed"

julia-lint:
	@echo "[Julia] Running Aqua.jl and JET.jl checks..."
	julia --project=$(JULIA_PROJECT) -e '\
		using Pkg; \
		Pkg.add(["Aqua", "JET"]); \
		using GIVPOptimizer, Aqua, JET; \
		Aqua.test_all(GIVPOptimizer; ambiguities=(broken=false,), stale_deps=(ignore=[:JSON, :Aqua, :JET],), piracies=(broken=false,)); \
		report_package("GIVPOptimizer")'
	@echo "[Julia] ✓ Aqua/JET lint passed"

julia-coverage:
	@echo "[Julia] Running coverage gate (>=95%)..."
	JULIA_NUM_THREADS=2 julia --project=$(JULIA_PROJECT) -e 'using Pkg; Pkg.test(; coverage=true)'
	julia -e '\
		using Pkg; \
		Pkg.add("CoverageTools"); \
		using CoverageTools; \
		coverage = process_folder("julia/src"); \
		LCOV.writefile("julia-lcov.info", coverage)'
	julia -e '\
		using Pkg; \
		Pkg.add("CoverageTools"); \
		using CoverageTools; \
		cov = process_folder("julia/src"); \
		let \
			hit = 0; \
			total = 0; \
			for s in cov \
				for c in s.coverage \
					c === nothing && continue; \
					total += 1; \
					c > 0 && (hit += 1); \
				end; \
			end; \
			pct = total > 0 ? hit / total * 100.0 : 0.0; \
			println("[Julia] Coverage: $(round(pct; digits=1))%  ($hit / $total lines)"); \
			pct >= 95.0 || (println("[Julia] Coverage below 95% threshold (got $(round(pct; digits=1))%)"); exit(1)); \
		end'
	@echo "[Julia] ✓ Coverage gate passed"

julia-all: julia-test julia-format-check julia-lint julia-coverage
	@echo "[Julia] ✓✓✓ All quality gates passed"

# ──────────────────────────────────────────────────────────────────────────────
# Rust
# ──────────────────────────────────────────────────────────────────────────────

RUST_DIR := rust

.PHONY: rust-lint rust-format-check rust-test rust-coverage rust-all

rust-lint:
	@echo "[Rust] Running cargo clippy..."
	cd $(RUST_DIR) && cargo clippy --all-targets --all-features -- -D warnings
	@echo "[Rust] ✓ cargo clippy passed"

rust-format-check:
	@echo "[Rust] Checking cargo fmt (dry-run)..."
	cd $(RUST_DIR) && cargo fmt --all -- --check
	@echo "[Rust] ✓ cargo fmt check passed"

rust-test:
	@echo "[Rust] Running cargo test..."
	cd $(RUST_DIR) && cargo test --verbose
	@echo "[Rust] ✓ cargo test passed"

rust-coverage:
	@echo "[Rust] Running coverage gate (>=90%)..."
	cd $(RUST_DIR) && cargo llvm-cov --all-features --lcov --output-path lcov.info
	@hit=$$(grep '^LH:' $(RUST_DIR)/lcov.info | awk -F: '{s+=$$2} END {print s+0}'); \
	 total=$$(grep '^LF:' $(RUST_DIR)/lcov.info | awk -F: '{s+=$$2} END {print s+0}'); \
	 if [ "$$total" -eq 0 ]; then \
	 	echo "[Rust] No coverage data found in $(RUST_DIR)/lcov.info"; \
	 	exit 1; \
	 fi; \
	 pct=$$(awk "BEGIN {printf \"%.1f\", $$hit / $$total * 100}"); \
	 echo "[Rust] Coverage: $${pct}% ($$hit / $$total lines)"; \
	 awk "BEGIN { if ($$hit / $$total * 100 < 90.0) { print \"[Rust] Coverage below 90% threshold (got $${pct}%)\"; exit 1 } }"
	@echo "[Rust] ✓ Coverage gate passed"

rust-all: rust-format-check rust-lint rust-test rust-coverage
	@echo "[Rust] ✓✓✓ All quality gates passed"

# ──────────────────────────────────────────────────────────────────────────────
# R
# ──────────────────────────────────────────────────────────────────────────────

R_DIR := r

.PHONY: r-lint r-format-check r-coverage r-all

r-lint:
	@echo "[R] Running lintr..."
	Rscript -e "lintr::lint_package('$(R_DIR)', linters = lintr::linters_with_defaults())"
	@echo "[R] ✓ lintr passed"

r-format-check:
	@echo "[R] Checking R code formatting (dry-run)..."
	Rscript -e "\
		if (!requireNamespace('formatR', quietly = TRUE)) quit(status = 1); \
		files <- list.files('$(R_DIR)/R', pattern='\\\\.[Rr]$$', full.names=TRUE); \
		bad <- vapply(files, function(f) !identical(readLines(f, warn=FALSE), formatR::tidy_source(f, output=FALSE)$$text.tidy), logical(1)); \
		if (any(bad)) { \
			cat('Unformatted files:\n', paste(files[bad], collapse='\n'), '\n'); \
			quit(status=1); \
		}"
	@echo "[R] ✓ R format check passed"

r-coverage:
	@echo "[R] Running coverage gate (>=90%)..."
	Rscript -e "\
		cov <- covr::package_coverage(path = '$(R_DIR)'); \
		pct <- covr::percent_coverage(cov); \
		cat(sprintf('[R] Coverage: %.1f%%\n', pct)); \
		covr::to_cobertura(cov, filename = 'coverage-r.xml'); \
		if (pct < 90) stop(sprintf('Coverage below 90%% threshold (got %.1f%%)', pct)) \
	"
	@echo "[R] ✓ Coverage gate passed"

r-all: r-lint r-format-check r-coverage
	@echo "[R] ✓✓✓ All quality gates passed"

# ──────────────────────────────────────────────────────────────────────────────
# Combined / Top-level targets
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: quality-all local-ci

quality-all: python-all rust-all julia-all cpp-all r-all
	@echo ""
	@echo "╔════════════════════════════════════════════════════════════╗"
	@echo "║  ✓ All quality gates passed across all languages           ║"
	@echo "╚════════════════════════════════════════════════════════════╝"

local-ci:
	@echo "[Local CI] Running docker-compose equivalent..."
	bash scripts/local-ci/run.sh python rust julia cpp r
