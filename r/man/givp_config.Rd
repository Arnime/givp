% SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
% SPDX-License-Identifier: MIT
\name{givp_config}
\alias{givp_config}
\alias{GIVPConfig}
\title{Create or represent a GIVP configuration}
\usage{
givp_config(...)

GIVPConfig
}
\arguments{
  \item{...}{Fields to override in \code{GIVPConfig}.}
}
\value{A \code{GIVPConfig} R6 object.}
\description{\code{givp_config()} builds a validated configuration object used by the optimizer.}
\details{Instantiate directly with \code{GIVPConfig\$new(...)} when needed.}
