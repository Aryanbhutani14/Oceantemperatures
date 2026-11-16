# data/

Only `data/audit/` (small catalogue/metadata JSON from Phase 0) is committed.
Everything else is created by the pipeline and git-ignored.

```text
data/
├── audit/       # Phase 0 catalogue metadata (committed)
├── raw/         # untouched downloads, one folder per source, read-only after download
├── interim/     # per-source harmonised Zarr on the canonical grid
├── processed/   # cube.zarr (inputs + target + masks), features.zarr
└── final/       # ML-ready Parquet tables, eval index, ARGO matchups
```

Provenance for every file is documented in `docs/provenance.md`.
