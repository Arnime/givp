// SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
// SPDX-License-Identifier: MIT
#pragma once

#include <algorithm>
#include <cmath>
#include <numeric>
#include <utility>
#include <vector>

#include "cache.hpp"
#include "grasp.hpp"
#include "helpers.hpp"

namespace givp::detail {

struct PerturbStrength {
    std::size_t value;
};

struct VndMaxIterations {
    std::size_t value;
};

template <typename RngT> struct VndContext {
    const std::vector<double> &lower;
    const std::vector<double> &upper;
    std::optional<EvaluationCache> &cache;
    std::size_t half;
    RngT &rng;
    const Deadline &deadline;
};

// ── Per-variable move primitives ──────────────────────────────────────────────

template <typename F, typename RngT>
static std::pair<double, bool> try_integer_moves(std::size_t idx, std::vector<double> &solution,
                                                 double best_cost, const F &func,
                                                 const VndContext<RngT> &ctx) {

    double base = std::round(solution[idx]);
    double best = best_cost;
    bool improved = false;

    for (double delta : {-1.0, 0.0, 1.0}) {
        double val = std::round(clamp_val(base + delta, ctx.lower[idx], ctx.upper[idx]));
        if (std::abs(val - solution[idx]) < 1e-12)
            continue;
        double old = solution[idx];
        solution[idx] = val;
        double cost = evaluate_with_cache(solution, func, ctx.cache, ctx.half);
        if (cost < best) {
            best = cost;
            improved = true;
        } else {
            solution[idx] = old;
        }
    }
    return {best, improved};
}

template <typename F, typename RngT>
static std::pair<double, bool> try_continuous_move(std::size_t idx, std::vector<double> &solution,
                                                   double best_cost, const F &func,
                                                   VndContext<RngT> &ctx) {

    double span = ctx.upper[idx] - ctx.lower[idx];
    double delta = ctx.rng.uniform(-0.05, 0.05) * span;
    double new_val = clamp_val(solution[idx] + delta, ctx.lower[idx], ctx.upper[idx]);
    double old = solution[idx];
    solution[idx] = new_val;
    if (double cost = evaluate_with_cache(solution, func, ctx.cache, ctx.half); cost < best_cost)
        return {cost, true};
    solution[idx] = old;
    return {best_cost, false};
}

template <typename RngT>
static void perturb_index(std::vector<double> &solution, std::size_t idx, PerturbStrength strength,
                          VndContext<RngT> &ctx) {

    if (idx >= ctx.half) {
        double step = std::max(static_cast<double>(strength.value) / 2.0, 1.0);
        double delta = ctx.rng.uniform(-step, step);
        solution[idx] =
            std::round(clamp_val(solution[idx] + delta, ctx.lower[idx], ctx.upper[idx]));
    } else {
        double span = ctx.upper[idx] - ctx.lower[idx];
        double delta = ctx.rng.uniform(-0.15, 0.15) * span;
        solution[idx] = clamp_val(solution[idx] + delta, ctx.lower[idx], ctx.upper[idx]);
    }
}

// ── Neighborhoods ─────────────────────────────────────────────────────────────

template <typename F, typename RngT>
static std::pair<double, bool> neighborhood_flip(std::vector<double> &solution, double best_cost,
                                                 const F &func, std::vector<double> &sensitivity,
                                                 VndContext<RngT> &ctx) {

    std::size_t n = solution.size();
    std::vector<std::size_t> indices(n);
    std::iota(indices.begin(), indices.end(), std::size_t{0});
    std::sort(indices.begin(), indices.end(),
              [&](std::size_t a, std::size_t b) { return sensitivity[b] < sensitivity[a]; });

    double current_best = best_cost;
    bool any_improved = false;

    for (std::size_t vidx : indices) {
        if (expired(ctx.deadline))
            break;
        auto [nc, imp] = (vidx >= ctx.half)
                             ? try_integer_moves(vidx, solution, current_best, func, ctx)
                             : try_continuous_move(vidx, solution, current_best, func, ctx);
        if (imp) {
            sensitivity[vidx] = 0.9 * sensitivity[vidx] + (current_best - nc);
            current_best = nc;
            any_improved = true;
        }
    }
    return {current_best, any_improved};
}

template <typename F, typename RngT>
static std::pair<double, bool> neighborhood_swap(std::vector<double> &solution, double best_cost,
                                                 const F &func, VndContext<RngT> &ctx) {

    std::size_t n = solution.size();
    double current_best = best_cost;
    bool any_improved = false;
    std::size_t max_attempts = std::min(std::size_t{50}, n * (n - 1) / 2);

    for (std::size_t attempt = 0; attempt < max_attempts; ++attempt) {
        if (expired(ctx.deadline))
            break;
        std::size_t i = ctx.rng.uniform_index(0, n - 1);
        std::size_t j = ctx.rng.uniform_index(0, n - 1);
        if (i == j)
            continue;
        double old_i = solution[i];
        double old_j = solution[j];
        perturb_index(solution, i, PerturbStrength{4}, ctx);
        perturb_index(solution, j, PerturbStrength{4}, ctx);
        normalize_integer_tail(solution, ctx.half);
        double cost = evaluate_with_cache(solution, func, ctx.cache, ctx.half);
        if (cost < current_best) {
            current_best = cost;
            any_improved = true;
        } else {
            solution[i] = old_i;
            solution[j] = old_j;
        }
    }
    return {current_best, any_improved};
}

template <typename F, typename RngT>
static std::pair<double, bool> neighborhood_multiflip(std::vector<double> &solution,
                                                      double best_cost, const F &func,
                                                      VndContext<RngT> &ctx) {

    std::size_t n = solution.size();
    std::size_t k = std::min(std::size_t{3}, n);
    double current_best = best_cost;
    bool any_improved = false;

    for (std::size_t attempt = 0; attempt < 50; ++attempt) {
        if (expired(ctx.deadline))
            break;
        std::vector<double> backup = solution;
        std::vector<std::size_t> indices(n);
        std::iota(indices.begin(), indices.end(), std::size_t{0});
        // Fisher-Yates partial shuffle for k elements
        for (std::size_t i = 0; i < k; ++i) {
            std::size_t j = ctx.rng.uniform_index(i, n - 1);
            std::swap(indices[i], indices[j]);
        }
        for (std::size_t i = 0; i < k; ++i)
            perturb_index(solution, indices[i], PerturbStrength{4}, ctx);
        normalize_integer_tail(solution, ctx.half);
        double cost = evaluate_with_cache(solution, func, ctx.cache, ctx.half);
        if (cost < current_best) {
            current_best = cost;
            any_improved = true;
        } else {
            solution = backup;
        }
    }
    return {current_best, any_improved};
}

// ── VND: Variable Neighborhood Descent ───────────────────────────────────────

template <typename F, typename RngT>
double local_search_vnd(const F &func, std::vector<double> &solution, double current_cost,
                        VndMaxIterations max_iter, VndContext<RngT> &ctx) {

    std::size_t n = solution.size();
    std::vector<double> sensitivity(n, 0.0);
    double best_cost = current_cost;
    std::size_t no_improve_flip_count = 0;
    const std::size_t no_improve_limit = 5;

    for (std::size_t iter = 0; iter < max_iter.value; ++iter) {
        if (expired(ctx.deadline))
            break;

        // Decay sensitivity
        for (auto &s : sensitivity)
            s *= 0.9;

        // Neighborhood 1: flip
        auto [c1, imp1] = neighborhood_flip(solution, best_cost, func, sensitivity, ctx);
        best_cost = c1;

        if (!imp1) {
            ++no_improve_flip_count;
            // Neighborhood 2: swap
            auto [c2, imp2] = neighborhood_swap(solution, best_cost, func, ctx);
            best_cost = c2;

            if (!imp2 && no_improve_flip_count >= no_improve_limit) {
                // Neighborhood 3: multiflip
                auto [c3, imp3] = neighborhood_multiflip(solution, best_cost, func, ctx);
                best_cost = c3;
                (void)imp3;
            }
        }
    }
    return best_cost;
}

} // namespace givp::detail
