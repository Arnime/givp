# SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
# SPDX-License-Identifier: MIT

FROM python@sha256:e6ec78c9345b8e0a2d105a820bd3b4fd4e85acf5ddddf19d5c456c29164b121e

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    bash \
    build-essential \
    ca-certificates \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
