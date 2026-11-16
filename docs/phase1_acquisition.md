# Phase 1: Data acquisition (completed 2026-11-17)

## What was downloaded

All sources cover 2021-01-01 → 2021-12-31. Each was subset on the server to the padded box 44.5–105.5°E, 4.5–30.5°N (domain + 0.5°).

| Source | Files | Size | Native shape per file | Variables (native units) |
|---|---|---|---|---|
| GLORYS 0.25° (target) | 12 monthly | 1,766 MB | time × 47 depths (0.51–1045.85 m) × 105 lat × 245 lon | `thetao_glor` (°C, potential temperature) |
| GLORYS12 climatology | 1 | 198 MB | 12 months × 36 depths (0.49–1062.44 m) × 313 × 733 | `thetao` (°C) |
| OSTIA SST | 12 | 464 MB | time × 520 × 1220 (0.05°) | `analysed_sst` (**kelvin**) |
| Multi-obs SSS | 12 | 149 MB | time × 1 depth × 208 × 488 (0.125°) | `sos` (practical salinity, "1e-3") |
| DUACS SLA + currents | 12 | 445 MB | time × 208 × 488 (0.125°) | `sla` (m), `ugos`, `vgos` (m/s) |
| CMEMS L4 winds | 12 | 3,557 MB | 744 hourly steps × 208 × 488 (0.125°) | `eastward_wind`, `northward_wind` (m/s) |
| ARGO profiles | 4,071 | 243 MB | one NetCDF per profile (99 floats) | TEMP, PSAL, PRES + QC flags |
| IBTrACS North Indian | 1 CSV | 28 MB | n/a | cyclone tracks |
| **Total** | | **≈ 6.8 GB** | | |

## How (reproducible)

- **CMEMS:** `scripts/download/download_cmems.py --source <name>`. It works month by month and writes `.part.nc` files that are renamed only when complete, so a run can be restarted safely. Each request is logged in `data/raw/download_log.jsonl`.
- **ARGO + IBTrACS:** `scripts/download/download_argo_ibtracs.py`.
  - The profile list comes from the Argo GDAC index, filtered to the domain and 2021, and is saved as `data/raw/argo/selection_2021.csv`.
  - One file timed out on the first pass and succeeded on retry.
- **Verification:** `scripts/download/verify_raw.py` writes a SHA-256 manifest (`data/raw/manifest.json`) and a summary (`data/audit/raw_verification.json`).

## Verification results

All checks passed for all 72 gridded files, 4,071 ARGO files and the IBTrACS CSV:
- every file opens
- variables and units are as expected
- time steps are complete (daily = days in month; winds = 24 × days; climatology = 12)
- no duplicate timestamps
- the domain is fully covered
- the target reaches below 1000 m

## Findings to handle in Phase 2 (recorded, nothing changed in the raw files)

1. **OSTIA contains inland lakes.** 18 cells near 0 °C at 28.5–29.6°N are Tibetan lakes, for example around 28.5°N 90.4°E. None lie in the GLORYS ocean. They are removed by the canonical ocean mask, not by deleting values.
2. **Winds have values over land** (no NaN), because the L4 product is gap-filled with a model. The ocean mask is applied after regridding.
3. **About 50% of the box is land**, consistent across products (NaN fraction 0.50–0.52), so roughly 12,000 ocean cells are expected. The exact count comes in Phase 2.
4. **The 0 m target uses the shallowest native level** (0.506 m), as planned.
5. **SSS has a singleton depth axis.** It will be squeezed.
6. **Salinity range** 27.6–40.0 PSU is physical: 40 is the Persian Gulf/Red Sea margin, and fresh values come from Bay of Bengal river plumes.
