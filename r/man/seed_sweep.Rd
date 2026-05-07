% SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
% SPDX-License-Identifier: MIT
\name{seed_sweep}
\alias{seed_sweep}
\alias{sweep_summary}
\title{Run and summarize multi-seed experiments}
\usage{
seed_sweep(
  func,
  bounds,
  n_runs = 30L,
  config = NULL,
  num_vars = NULL,
  direction = NULL,
  verbose = FALSE
)

sweep_summary(sweep_results)
}
\arguments{
  \item{func}{Objective function.}
  \item{bounds}{Variable bounds.}
  \item{n_runs}{Number of seeds/runs.}
  \item{config}{Optional \code{GIVPConfig}.}
  \item{num_vars}{Optional number of variables.}
  \item{direction}{Optional optimization direction.}
  \item{verbose}{Verbose mode.}
  \item{sweep_results}{Result list returned by \code{seed_sweep()}.}
}
\value{\code{seed_sweep()} returns a named list of \code{givp_result}; \code{sweep_summary()} returns aggregate statistics.}
\description{Utilities for reproducible seeded runs and summary statistics.}
