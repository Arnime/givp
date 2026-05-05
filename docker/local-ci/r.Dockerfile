# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT

FROM rocker/r-ver@sha256:20ede1f846d2423b483b1019a499cc0f8c1d15192f47812c92d0900af4029039

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    bash \
    build-essential \
    ca-certificates \
    git \
    libcurl4-openssl-dev \
    libssl-dev \
    libuv1-dev \
    libxml2-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
