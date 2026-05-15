% SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
% SPDX-License-Identifier: MIT
\name{givp}
\alias{givp}
\title{Optimize with GIVP}
\usage{
givp(
  func,
  bounds,
  num_vars = NULL,
  minimize = NULL,
  direction = NULL,
  config = NULL,
  initial_guess = NULL,
  initial_guesses = NULL,
  iteration_callback = NULL,
  seed = NULL,
  verbose = FALSE
)
}
\arguments{
  \item{func}{Objective function receiving a numeric vector and returning a scalar.}
  \item{bounds}{Variable bounds.}
  \item{num_vars}{Optional number of variables.}
  \item{minimize}{Optional boolean for optimization direction.}
  \item{direction}{Optional string (\code{"minimize"} or \code{"maximize"}).}
  \item{config}{Optional \code{GIVPConfig} object.}
  \item{initial_guess}{Optional warm-start vector.}
  \item{initial_guesses}{Optional list of warm-start vectors.}
  \item{iteration_callback}{Optional callback per iteration.}
  \item{seed}{Optional RNG seed.}
  \item{verbose}{Enable verbose output.}
}
\value{A \code{givp_result} object.}
\description{Functional entry point for the R port, mirroring the Python API.}
