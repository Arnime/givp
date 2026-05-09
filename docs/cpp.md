<!-- SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior -->
<!-- SPDX-License-Identifier: MIT -->

# C++

`givp` is also available as a native C++17 header-only library, providing the
same GRASP-ILS-VND with Path Relinking algorithm with a low-overhead API.

## Installation

Install via vcpkg:

```bash
vcpkg install givp
```

In your CMake project:

```cmake
find_package(givp CONFIG REQUIRED)
target_link_libraries(my_app PRIVATE givp::givp)
```

Or build from a local clone of the repository:

```bash
cmake -S cpp -B cpp/build/default -DGIVP_BUILD_TESTS=ON -DGIVP_BUILD_BENCHMARKS=OFF
cmake --build cpp/build/default
ctest --test-dir cpp/build/default --output-on-failure
```

To install the CMake package config files (`givpConfig.cmake`,
`givpConfigVersion.cmake`, and exported targets), run:

```bash
cmake -S cpp -B cpp/build/package-install -DGIVP_BUILD_TESTS=OFF -DGIVP_BUILD_BENCHMARKS=OFF
cmake --build cpp/build/package-install
cmake --install cpp/build/package-install --prefix ./cpp/build/package-install/install
```

Then point your consumer project to that prefix:

```bash
cmake -S my_app -B my_app/build -DCMAKE_PREFIX_PATH="$(pwd)/cpp/build/package-install/install"
cmake --build my_app/build
```

Requires C++17 and CMake 3.21+.

## Quick start

```cpp
#include <givp/givp.hpp>
#include <vector>

int main() {
    auto sphere = [](const std::vector<double>& x) {
        double s = 0.0;
        for (double v : x) s += v * v;
        return s;
    };

    std::vector<std::pair<double, double>> bounds(10, {-5.12, 5.12});
    givp::GivpConfig cfg;
    cfg.seed = 42;
    cfg.integer_split = 10; // all continuous

    auto result = givp::givp(sphere, bounds, cfg);
    return result.success ? 0 : 1;
}
```

## Maximize

```cpp
givp::GivpConfig cfg;
cfg.direction = givp::Direction::Maximize;
auto result = givp::givp(my_score, bounds, cfg);
```

## Configuration

All core hyper-parameters are exposed via `givp::GivpConfig`:

```cpp
givp::GivpConfig cfg;
cfg.max_iterations = 50;
cfg.vnd_iterations = 100;
cfg.ils_iterations = 10;
cfg.elite_size = 7;
cfg.adaptive_alpha = true;
cfg.time_limit = 30.0;
cfg.seed = 42;
```

## Mixed continuous/integer problems

Use `integer_split` as the number of continuous variables. Variables after this
index are treated as integer variables.

```cpp
std::size_t n_cont = 12;
std::size_t n_int = 8;
std::vector<std::pair<double, double>> bounds;
bounds.insert(bounds.end(), n_cont, {-5.0, 5.0});
bounds.insert(bounds.end(), n_int, {0.0, 4.0});

givp::GivpConfig cfg;
cfg.integer_split = n_cont;
auto result = givp::givp(my_objective, bounds, cfg);
```

## Result type

`givp::givp(...)` returns an `OptimizeResult` with the following fields:

| Field | Meaning |
|---|---|
| `x` | Best solution vector. |
| `fun` | Objective value at `x` (original user sign). |
| `nit` | Number of iterations executed. |
| `nfev` | Number of objective evaluations. |
| `success` | Whether at least one feasible solution was found. |
| `message` | Human-readable termination message. |
| `direction` | Optimization direction used. |
| `meta` | Extra metadata map. |

## Errors

The C++ API provides a typed exception hierarchy rooted at `givp::GivpError`:

- `givp::InvalidBounds`
- `givp::InvalidInitialGuess`
- `givp::InvalidConfig`
- `givp::EvaluatorError`
- `givp::EmptyPool`

## Running benchmarks

```bash
cmake -S cpp -B cpp/build/benchmarks -DGIVP_BUILD_TESTS=OFF -DGIVP_BUILD_BENCHMARKS=ON
cmake --build cpp/build/benchmarks
./cpp/build/benchmarks/benchmarks/givp_benchmarks
```

## Literature comparison experiment

The C++ port also includes a reproducible multi-run experiment binary with
JSON output compatible with the Python and Julia report generators:

```bash
cmake -S cpp -B cpp/build/benchmarks -DGIVP_BUILD_TESTS=OFF -DGIVP_BUILD_BENCHMARKS=ON
cmake --build cpp/build/benchmarks --target givp_literature_comparison
./cpp/build/benchmarks/benchmarks/givp_literature_comparison \
    --n-runs 30 --dims 10 --output cpp/benchmarks/literature_comparison.json
```

Latest notebook run results for this experiment (C++, 10-D, 30 seeds,
GIVP-full vs GRASP-only) are documented in the comparison page under the
"C++" section.

## Coverage

The CI enforces a minimum of 90% line coverage for the C++ port.

## Maintainer operations

Operational and packaging guides are kept under `cpp/docs/` so the public page
stays focused on consuming the library.

- `cpp/README_INTELLISENSE.md` for local CMake and IntelliSense setup
- `cpp/docs/LOCAL_TESTING_GUIDE.md` for local vcpkg and Conan validation
- `cpp/docs/RELEASE_AUTOMATION.md` for tag-driven release workflow
- `cpp/docs/VCPKG_NOTES.md` for vcpkg registry submission
- `cpp/docs/CONAN_NOTES.md` for Conan Center submission

## API parity with Python

| Feature | Python | C++ |
|---|---|---|
| GRASP construction | ✓ | ✓ |
| VND local search | ✓ | ✓ |
| ILS perturbation | ✓ | ✓ |
| Path Relinking | ✓ | ✓ |
| Elite pool | ✓ | ✓ |
| Convergence monitor | ✓ | ✓ |
| LRU evaluation cache | ✓ | ✓ |
| Adaptive alpha | ✓ | ✓ |
| Time budget | ✓ | ✓ |
| Mixed integer/continuous | ✓ | ✓ |
| Warm start | ✓ | ✓ |
| Reproducible (`seed=`) | ✓ | ✓ |
