// SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
// SPDX-License-Identifier: MIT
#pragma once

#include <algorithm>
#include <cmath>
#include <optional>
#include <utility>
#include <vector>

#include "cache.hpp"
#include "helpers.hpp"

namespace givp::detail {

// ── Adaptive alpha ────────────────────────────────────────────────────────────

struct AlphaScheduleParams {
    std::size_t iter_idx;
    std::size_t max_iterations;
    double alpha_min;
    double alpha_max;
    bool adaptive;
    double alpha;
};

inline double get_current_alpha(const AlphaScheduleParams &params) {
    if (!params.adaptive)
        return params.alpha;
    double progress = static_cast<double>(params.iter_idx) /
                      static_cast<double>(std::max(params.max_iterations, std::size_t{1}));
    return params.alpha_min + (params.alpha_max - params.alpha_min) * progress;
}

// ── Cached evaluation ─────────────────────────────────────────────────────────

template <typename F>
double evaluate_with_cache(const std::vector<double> &candidate, const F &func,
                           std::optional<EvaluationCache> &cache, std::size_t half) {
    if (cache) {
        if (auto cached = cache->get(candidate, half); cached.has_value())
            return *cached;
        double cost = safe_evaluate(func, candidate);
        cache->put(candidate, cost, EvaluationCache::HalfIndex{half});
        return cost;
    }
    return safe_evaluate(func, candidate);
}

// ── RCL selection ─────────────────────────────────────────────────────────────

template <typename RngT>
static std::size_t select_from_rcl(const std::vector<double> &costs, double alpha, RngT &rng) {
    double min_cost = *std::min_element(costs.begin(), costs.end());
    double max_cost = *std::max_element(costs.begin(), costs.end());
    double threshold = min_cost + alpha * (max_cost - min_cost);

    std::vector<std::size_t> candidates;
    for (std::size_t i = 0; i < costs.size(); ++i)
        if (costs[i] <= threshold)
            candidates.push_back(i);

    if (candidates.empty())
        return 0;
    return candidates[rng.uniform_index(0, candidates.size() - 1)];
}

// ── Candidate builders ────────────────────────────────────────────────────────

template <typename RngT> static double sample_integer_from_bounds(double lo, double hi, RngT &rng) {
    std::int64_t lo_i = static_cast<std::int64_t>(std::ceil(lo));
    std::int64_t hi_i = static_cast<std::int64_t>(std::floor(hi));
    if (lo_i > hi_i)
        return std::round((lo + hi) / 2.0);
    return static_cast<double>(rng.uniform_int(lo_i, hi_i));
}

struct CandidateBuildParams {
    std::size_t num_vars;
    std::size_t half;
    const std::vector<double> &lower;
    const std::vector<double> &upper;
};

template <typename RngT>
static std::vector<double> build_random_candidate(const CandidateBuildParams &params, RngT &rng) {
    std::vector<double> sol(params.num_vars);
    for (std::size_t i = 0; i < params.half; ++i)
        sol[i] = rng.uniform(params.lower[i], params.upper[i]);
    for (std::size_t i = params.half; i < params.num_vars; ++i)
        sol[i] = sample_integer_from_bounds(params.lower[i], params.upper[i], rng);
    return sol;
}

template <typename RngT>
static std::vector<double> build_heuristic_candidate(const CandidateBuildParams &params,
                                                     RngT &rng) {
    std::vector<double> sol(params.num_vars);
    for (std::size_t i = 0; i < params.half; ++i) {
        double mid = (params.lower[i] + params.upper[i]) / 2.0;
        double span = params.upper[i] - params.lower[i];
        double noise = rng.uniform(-0.15, 0.15) * span;
        sol[i] = clamp_val(mid + noise, params.lower[i], params.upper[i]);
    }
    for (std::size_t i = params.half; i < params.num_vars; ++i)
        sol[i] = sample_integer_from_bounds(params.lower[i], params.upper[i], rng);
    return sol;
}

struct GraspConstructParams {
    const std::vector<double> *initial_guess;
    double alpha;
    std::size_t half;
    std::size_t num_candidates;
};

struct GraspRunContext {
    std::size_t num_vars;
    const std::vector<double> &lower;
    const std::vector<double> &upper;
    std::optional<EvaluationCache> &cache;
    const Deadline &deadline;
};

// ── GRASP construction ────────────────────────────────────────────────────────

template <typename F, typename RngT>
std::pair<std::vector<double>, double> construct_grasp(const F &func,
                                                       const GraspConstructParams &params,
                                                       const GraspRunContext &ctx, RngT &rng) {

    std::vector<std::vector<double>> candidates;
    std::vector<double> costs;
    candidates.reserve(params.num_candidates);
    costs.reserve(params.num_candidates);
    const CandidateBuildParams build_params{ctx.num_vars, params.half, ctx.lower, ctx.upper};

    // Optional initial guess as first candidate
    if (params.initial_guess) {
        auto sol = *params.initial_guess;
        normalize_integer_tail(sol, params.half);
        double cost = evaluate_with_cache(sol, func, ctx.cache, params.half);
        candidates.push_back(std::move(sol));
        costs.push_back(cost);
    }

    // One heuristic candidate
    if (candidates.size() < params.num_candidates) {
        auto sol = build_heuristic_candidate(build_params, rng);
        normalize_integer_tail(sol, params.half);
        double cost = evaluate_with_cache(sol, func, ctx.cache, params.half);
        candidates.push_back(std::move(sol));
        costs.push_back(cost);
    }

    // Fill rest with random candidates
    while (candidates.size() < params.num_candidates) {
        if (expired(ctx.deadline))
            break;
        auto sol = build_random_candidate(build_params, rng);
        normalize_integer_tail(sol, params.half);
        double cost = evaluate_with_cache(sol, func, ctx.cache, params.half);
        candidates.push_back(std::move(sol));
        costs.push_back(cost);
    }

    std::size_t idx = select_from_rcl(costs, params.alpha, rng);
    double selected_cost = costs[idx];
    auto selected_sol = std::move(candidates[idx]);
    return {std::move(selected_sol), selected_cost};
}

} // namespace givp::detail
