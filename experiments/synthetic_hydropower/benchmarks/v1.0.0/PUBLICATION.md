# Publication package — v1.0.0

This document is the release checklist for the frozen
`synthetic-hydropower-v1.0.0` benchmark. The root
[`benchmark_manifest.json`](benchmark_manifest.json) is the authoritative list
of canonical inputs, results and figures.

## Scope and licenses

- The benchmark artefacts in this directory use [CC BY 4.0](LICENSE-DATA.md).
- The GIVP source code remains under the repository's [MIT License](../../../../LICENSE).
- Local outputs, virtual environments, build directories, caches and logs are
  deliberately excluded from publication packages.
- The provenance record documents a synthetic academic approximation anchored
  in public reference ranges. It excludes SOG2 code, operational series,
  internal tables and proprietary coefficients. It is not a legal opinion.

## Create and verify the packages

From a clean, committed repository state, run the frozen regression tests and
create packages from the exact commit to be cited:

```powershell
poetry -C python run pytest -m benchmark_regression tests -v --no-cov --override-ini="addopts="
python experiments/synthetic_hydropower/scripts/create_publication_bundle.py `
  --repository-root <repository-root> `
  --version v1.0.0 `
  --output-dir <publication-output-directory>
```

The command creates:

- `synthetic-hydropower-v1.0.0-source-<commit>.zip` for Zenodo, containing the
  complete tracked GIVP source snapshot needed for reproduction;
- `synthetic-hydropower-v1.0.0-hydroshare-<commit>.zip`, containing only the
  benchmark's hydrological artefacts and publication metadata;
- `SHA256SUMS` and `publication.json`, identifying the commit, archive hashes
  and verification status.

Do not regenerate, edit or re-compress an archive after its hash has been
recorded. A new commit requires a new package and, after formal publication, a
new benchmark version.

## Zenodo record — canonical citation

Create a manual **Dataset** deposit with the following metadata:

| Field | Value |
| --- | --- |
| Title | Synthetic Two-Plant Hydropower Balance Benchmark |
| Version | 1.0.0 |
| License | CC BY 4.0 |
| Creator | Arnaldo Mendes Pires Junior |
| Keywords | hydropower; water balance; synthetic benchmark; optimization; GRASP; reproducibility |
| Related identifier | GitHub repository and exact commit archived in `publication.json` |

Upload the Zenodo source ZIP, its `SHA256SUMS`, `publication.json`, this
publication guide and the benchmark `CITATION.cff`. After publishing, record
the version DOI in this document and in the experiment README. This DOI is the
primary citation for the benchmark.

**Zenodo version DOI:** pending manual deposit  
**Zenodo concept DOI:** pending manual deposit

## HydroShare resource — hydrology companion

Create one public HydroShare resource from the HydroShare ZIP. Use the same
title and version, the CC BY 4.0 license, the abstract from `CITATION.cff`, and
metadata that describes a synthetic 24-hour, two-plant cascade rather than a
real operational system. Include units, the seven frozen scenarios, the two
protocols, limitations and the public references in `data_provenance.json`.

Add the Zenodo version DOI as a related resource and state that Zenodo is the
canonical archive and preferred citation. Review title, authorship, contents
and metadata before selecting **Publish**: HydroShare publication makes the
core content immutable and assigns a DOI.

**HydroShare resource URL:** pending manual deposit  
**HydroShare DOI:** pending manual publication

## Citation after deposit

Use the rendered citation from this directory's `CITATION.cff`, adding the
Zenodo version DOI. Cite the HydroShare DOI only when specifically referring to
the hydrology-focused companion resource.
