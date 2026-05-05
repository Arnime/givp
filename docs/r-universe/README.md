<!-- SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior -->
<!-- SPDX-License-Identifier: MIT -->
# r-universe bootstrap (Arnime)

This folder contains ready-to-copy files for the GitHub repository
`Arnime.r-universe.dev`.

## Files

- `packages.jsonc`: template for the package index used by r-universe.

## How to use

1. Create the GitHub repository `Arnime.r-universe.dev`.
2. Copy `packages.jsonc` from this folder to that repository.
3. Rename `packages.jsonc` to `packages.json`.
4. Commit and push.
5. Install the r-universe GitHub App from the Setup page.
6. Wait for the first build at `https://arnime.r-universe.dev`.

## Install command (after first successful build)

```r
install.packages(
  "givp",
  repos = c("https://arnime.r-universe.dev", "https://cloud.r-project.org")
)
```
