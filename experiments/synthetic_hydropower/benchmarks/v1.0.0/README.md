# Synthetic Hydropower Cascade Benchmark — v1.0.0

This is the only version of the academic benchmark. It shares the same cascade,
physical parameters, and seven frozen inflow series across two complementary
protocols.

## Protocols

### `deterministic_balance`

This is the canonical physical reference and does not run GIVP. For each
scenario, it crosses six constant power targets for A with six for B over a
24-hour period. This produces 36 combinations per scenario and 252 cases in
total.

The protocol records requested and delivered power, deficit, status, flows,
spill components, discharge, volumes, upstream and downstream levels, head,
penalties, and mass-balance residual. Its CSV files use six decimal places and
are reproducible from the frozen inflow series.

#### Verification by Clients in Other Languages

The protocol also provides an interoperability verification route: the R,
Julia, Rust, and C++ clients send the same 252 schedules to the Python worker
`synthetic-hydropower/v1`. Therefore, the physics remains unique and canonical
in Python; the other languages verify the local process, JSON, and result-to-
table transformation contracts.

| Client | Cases sent | Hourly series | Summary |
| --- | ---: | ---: | ---: |
| R | 252 | 12.096 ✓ | 252 ✓ |
| Julia | 252 | 12.096 ✓ | 252 ✓ |
| Rust | 252 | 12.096 ✓ | 252 ✓ |
| C++ | 252 | 12.096 ✓ | 252 ✓ |

Each response is compared with the CSV files in this directory using a `1e-6`
tolerance. Derived files are written to
`experiments/synthetic_hydropower/output/` and are not part of this frozen
benchmark, its checksums, or its `reference_results`. See the procedure in
[`clients/README.md`](../../clients/README.md).

### `givp_optimization`

This is a derived experiment that uses GIVP to select flow requests. The
hydraulic balance continues to be calculated by the same synthetic model. Its
results are stochastic references and may show small differences between
environments; they do not define the canonical deterministic-balance results.

## Structure

```text
v1.0.0/
  benchmark_definition.json
  benchmark_manifest.json
  data_provenance.json
  config/base.json
  inputs/inflows.csv
  protocols/
    deterministic_balance/
      definition.json
      protocol_manifest.json
      inputs/power_schedules.csv
      reference_results/
      figures/
    givp_optimization/
      definition.json
      protocol_manifest.json
      reference_results/
      figures/
```

The root manifest records the SHA-256 values of all canonical JSON, CSV, and
PNG files. Each protocol also has its own definition and manifest, making clear
whether a result came from deterministic equations or a GIVP execution.

## Citation and Publication

This benchmark is an academic product distinct from the GIVP software. Its
data, results, figures, and documentation are licensed under
[CC BY 4.0](LICENSE-DATA.md); the GIVP source code remains under the MIT license
at the repository root. The benchmark-specific citation is in
[`CITATION.cff`](CITATION.cff).

Zenodo is the canonical archive and the preferred DOI for citation:
<https://doi.org/10.5281/zenodo.22185079>. The supplementary HydroShare resource
for the hydrology community is published at
<https://doi.org/10.4211/hs.4d1e221b0638437f98847addc3e709c6>.

The procedure, metadata, scope of the two packages, and verification steps are
described in [`PUBLICATION.md`](PUBLICATION.md). It generates files from an
exact Git commit and revalidates this manifest's checksums inside the ZIP files
before any submission.

## Provenance and Independence

The parameters are synthetic and perturbed, anchored in publicly available
ranges. Plants A and B are academic approximations inspired by published
information about Monte Claro and 14 de Julho, without representing their
official operation.

No SOG2 code, historical series, operating table, or proprietary coefficient has
been incorporated. This organization documents technical independence, but it
does not constitute legal advice and does not replace analysis of patents,
contracts, or confidentiality obligations.
