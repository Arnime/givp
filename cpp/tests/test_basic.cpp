// SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
// SPDX-License-Identifier: MIT

#include <catch2/catch_test_macros.hpp>

#include <givp/config.hpp>
#include <givp/givp.hpp>
#include <givp/result.hpp>

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

using namespace givp;

// ── Objective functions ───────────────────────────────────────────────────────

static double sphere(const std::vector<double> &x) {
    double s = 0.0;
    for (auto v : x)
        s += v * v;
    return s;
}

static double rosenbrock(const std::vector<double> &x) {
    double s = 0.0;
    for (std::size_t i = 0; i + 1 < x.size(); ++i)
        s += 100.0 * (x[i + 1] - x[i] * x[i]) * (x[i + 1] - x[i] * x[i]) +
             (1.0 - x[i]) * (1.0 - x[i]);
    return s;
}

static double rastrigin(const std::vector<double> &x) {
    constexpr double pi = 3.14159265358979323846;
    double n = static_cast<double>(x.size());
    double s = 10.0 * n;
    for (auto xi : x)
        s += xi * xi - 10.0 * std::cos(2.0 * pi * xi);
    return s;
}

static std::vector<std::pair<double, double>> uniform_bounds(std::size_t dims, double lo,
                                                             double hi) {
    return std::vector<std::pair<double, double>>(dims, {lo, hi});
}

struct CfgSeed {
    std::uint64_t value;
};
struct CfgMaxIter {
    std::size_t value;
};
struct CfgIntSplit {
    std::size_t value;
};

static GivpConfig make_cfg(CfgSeed seed, CfgMaxIter max_iterations, CfgIntSplit integer_split) {
    GivpConfig cfg;
    cfg.seed = seed.value;
    cfg.max_iterations = max_iterations.value;
    cfg.integer_split = integer_split.value;
    return cfg;
}

// ── Smoke tests ───────────────────────────────────────────────────────────────

TEST_CASE("sphere 5D finds near-zero minimum", "[basic]") {
    auto bounds = uniform_bounds(5, -5.12, 5.12);
    auto cfg = make_cfg(CfgSeed{42}, CfgMaxIter{50}, CfgIntSplit{5}); // all continuous

    auto result = givp::givp(sphere, bounds, cfg);

    REQUIRE(result.success);
    REQUIRE(result.fun < 1.0);
    REQUIRE(result.x.size() == 5);
    REQUIRE(result.nfev > 0);
}

TEST_CASE("rosenbrock 5D converges", "[basic]") {
    auto bounds = uniform_bounds(5, -5.0, 10.0);
    auto cfg = make_cfg(CfgSeed{7}, CfgMaxIter{80}, CfgIntSplit{5});

    auto result = givp::givp(rosenbrock, bounds, cfg);

    REQUIRE(result.success);
    REQUIRE(result.fun < 500.0);
}

TEST_CASE("rastrigin 3D does not crash", "[basic]") {
    auto bounds = uniform_bounds(3, -5.12, 5.12);
    auto cfg = make_cfg(CfgSeed{99}, CfgMaxIter{30}, CfgIntSplit{3});

    auto result = givp::givp(rastrigin, bounds, cfg);

    REQUIRE(result.success);
    REQUIRE(result.x.size() == 3);
}

TEST_CASE("maximize direction negates correctly", "[basic]") {
    // Maximizing sphere means driving x toward bounds, fun > 0
    auto bounds = uniform_bounds(3, -5.12, 5.12);
    auto cfg = make_cfg(CfgSeed{1}, CfgMaxIter{30}, CfgIntSplit{3});
    cfg.direction = Direction::Maximize;

    auto result = givp::givp(sphere, bounds, cfg);

    REQUIRE(result.success);
    REQUIRE(result.fun > 0.0); // maximum of sphere on bounds > 0
    REQUIRE(result.direction == Direction::Maximize);
}

TEST_CASE("initial guess is accepted", "[basic]") {
    auto bounds = uniform_bounds(3, -5.0, 5.0);
    auto cfg = make_cfg(CfgSeed{5}, CfgMaxIter{30}, CfgIntSplit{3});
    cfg.initial_guess = std::vector<double>{0.1, 0.2, 0.3};

    REQUIRE_NOTHROW(givp::givp(sphere, bounds, cfg));
}

TEST_CASE("initial_guesses are accepted", "[basic]") {
    auto bounds = uniform_bounds(3, -5.0, 5.0);
    auto cfg = make_cfg(CfgSeed{6}, CfgMaxIter{30}, CfgIntSplit{3});
    cfg.initial_guesses = std::vector<std::vector<double>>{{1.5, 1.5, 1.5},
                                                            {0.2, -0.2, 0.3}};

    REQUIRE_NOTHROW(givp::givp(sphere, bounds, cfg));
}

TEST_CASE("time limit stops the run early", "[basic]") {
    auto bounds = uniform_bounds(10, -5.12, 5.12);
    auto cfg = make_cfg(CfgSeed{3}, CfgMaxIter{10'000},
                        CfgIntSplit{10}); // huge — time limit must fire first
    cfg.time_limit = 0.1;                 // 100 ms

    auto result = givp::givp(sphere, bounds, cfg);
    REQUIRE(result.success);
    // message should mention time
    REQUIRE(result.message.find("time") != std::string::npos);
    REQUIRE(result.termination == TerminationReason::TimeLimitReached);
}

TEST_CASE("result nfev matches evaluations roughly", "[basic]") {
    auto bounds = uniform_bounds(2, -1.0, 1.0);
    auto cfg = make_cfg(CfgSeed{0}, CfgMaxIter{5}, CfgIntSplit{2});
    cfg.use_cache = false;

    auto result = givp::givp(sphere, bounds, cfg);
    REQUIRE(result.nfev > 0);
    REQUIRE(result.nit >= 1);
    REQUIRE(result.nit <= cfg.max_iterations);
}

TEST_CASE("objective returning infinity is handled", "[basic]") {
    auto bad_func = [](const std::vector<double> &x) -> double {
        if (x[0] > 0)
            return std::numeric_limits<double>::infinity();
        return x[0] * x[0];
    };
    auto bounds = uniform_bounds(1, -5.0, 5.0);
    auto cfg = make_cfg(CfgSeed{2}, CfgMaxIter{20}, CfgIntSplit{1});

    REQUIRE_NOTHROW(givp::givp(bad_func, bounds, cfg));
}

TEST_CASE("objective throwing exception is handled", "[basic]") {
    auto throwing_func = [](const std::vector<double> &x) -> double {
        if (x[0] > 3.0)
            throw std::runtime_error("deliberate");
        return x[0] * x[0];
    };
    auto bounds = uniform_bounds(1, -5.0, 5.0);
    auto cfg = make_cfg(CfgSeed{11}, CfgMaxIter{20}, CfgIntSplit{1});

    REQUIRE_NOTHROW(givp::givp(throwing_func, bounds, cfg));
}
