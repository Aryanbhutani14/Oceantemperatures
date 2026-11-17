# Phase 2: Harmonisation onto the canonical grid (completed 2026-11-17)

Every source now sits on **one grid**: 101 lat × 241 lon cell centres (5–30°N, 45–105°E, 0.25°), **365 daily steps** (UTC calendar days, 2021), and for the target, **15 standard depths**. These are the outputs in `data/interim/` (not committed; rebuild with the commands below).

| File | Variables (canonical units) | Shape |
|---|---|---|
| `glorys_thetao.nc` | `thetao` °C (potential temperature): **target** | time 365 × depth 15 × 101 × 241 |
| `glorys_clim.nc` | `thetao_clim` °C: external monthly climatology | month 12 × depth 15 × 101 × 241 |
| `sst.nc` | `sst` °C | 365 × 101 × 241 |
| `sss.nc` | `sss` PSU | 365 × 101 × 241 |
| `ssh.nc` | `sla` m, `uo`, `vo` m s⁻¹ (geostrophic) | 365 × 101 × 241 |
| `winds.nc` | `u10`, `v10` m s⁻¹ | 365 × 101 × 241 |
| `masks.nc` | `ocean_mask`, `depth_valid` (per depth), `deepest_valid_depth` | 101 × 241 (×15) |

## Method (all steps in `scripts/harmonise/harmonise.py`)

1. **Rename** to canonical names: `lat`, `lon`, `time`, `depth`; `sst`, `sss`, `sla`, `uo`, `vo`, `u10`, `v10`, `thetao`.
2. **Units, converted explicitly.** Each conversion runs only after the file's `units` attribute has been checked against an allowed list; otherwise the script stops.
   - OSTIA kelvin → °C (−273.15).
   - Salinity "1e-3" (practical salinity) is labelled PSU. No numerical change.
   - Everything else is already in canonical units.
3. **Coordinates:** latitude and longitude sorted ascending; longitude in [−180, 180).
4. **One spatial operator for every source:** first-order conservative (area-weighted overlap, `src/oceanembed_ml/grid.py`).

   | Source | What the operator reduces to |
   |---|---|
   | GLORYS 0.25° | **Identity** (asserted: one-to-one weights) |
   | GLORYS12 climatology 1/12° | **Exact 3×3 block mean** (nested cells) |
   | SSS, SSH, winds 0.125° | **Exact 2×2 block mean** (nested cells) |
   | OSTIA 0.05° | **Partial-cell area weighting**: edges are not nested, so a plain 5×5 mean would shift the field by 0.025° |

   Cells are weighted by cos(latitude). A canonical cell is NaN unless at least 50% of its area has valid data, so there is no extrapolation into land or gaps.

   **Unit tests** (`tests/test_regrid.py`, 6 passing) cover: identity, constant-field preservation, exact block mean, area-integral conservation, the NaN threshold, and vertical interpolation.
5. **Time:** UTC calendar day. Winds: the mean of 24 hourly fields, with **all 24 required** (otherwise NaN).
6. **Vertical (target and climatology):**
   - Linear interpolation between the two bracketing native levels.
   - 0 m = shallowest level (0.506 m).
   - **No extrapolation:** if either bracket is missing (below the seafloor), the value is NaN.
7. **Masks:**
   - `ocean_mask` = target finite at 0 m on **every** day.
   - `depth_valid[d]` = target finite at depth d on every day.
   - All inputs are set to NaN outside the ocean mask. This removes the land values in the winds and the Tibetan lakes in OSTIA.
8. **Physical-range QC:** impossible values → NaN and counted. Nothing is deleted silently.

## Results (`data/audit/harmonisation_qc.json`)

| | Value |
|---|---|
| Ocean cells | **11,880** of 24,341. No cell flips between land and ocean across days. |
| Valid cells by depth | 0 m: 11,880 · 50 m: 10,659 · 100 m: 9,967 · 200 m: 9,832 · 500 m: 9,602 · 1000 m: 9,188 (the continental shelf drops out) |
| Target range | 5.8 to 35.7 °C; 0 values removed |

| Input | Valid over ocean | Ocean cells never valid | Range | Out-of-range removed |
|---|---|---|---|---|
| SST | 99.8% | 20 (coastal) | 15.9–36.4 °C | 0 |
| SSS | 99.7% | 30 (coastal) | 26.0–40.0 PSU | 0 |
| SLA | 100% | 0 | −0.42 to 0.62 m | 0 |
| uo / vo | 99.9% | 8 | −2.0 to 2.6 m s⁻¹ | 0 |
| u10 / v10 | 100% | 0 | −17.7 to 19.7 m s⁻¹ | 0 |

The few coastal cells with no satellite data **stay NaN**. They are not filled; the models handle them later.

## Issue caught and fixed: real extremes vs errors

The first run used a 35 °C upper limit. It removed **863 target values**, and it would have removed **about 119,000 OSTIA values**. All of them were in the **Persian Gulf, June–September** (24–28°N, 50–57°E), where real summer SST reaches 35–36.7 °C. These are real ocean conditions, not errors, so the limit was raised to 38 °C (decision D-016). The rerun removes 0 values.

## Figures (`reports/figures/phase2/`)

| Figure | What it shows |
|---|---|
| `compare_sst.png`, `compare_sss.png`, `compare_sla.png`, `compare_u10.png`, `compare_thetao.png` | Native vs harmonised field on 2021-08-15. The structure is preserved: Somali/Oman upwelling, the warm Persian Gulf, Bay of Bengal freshening. |
| `masks.png` | Ocean mask and deepest valid depth |
| `mean_profile.png` | Domain-mean profile vs climatology. Variability peaks at **75–100 m (the thermocline)**, the hardest layer to predict. |

## Reproduce

```bash
.venv/Scripts/python -m pytest -q tests
.venv/Scripts/python scripts/harmonise/harmonise.py --source glorys     # first: builds masks
.venv/Scripts/python scripts/harmonise/harmonise.py --source all
.venv/Scripts/python scripts/harmonise/plot_phase2.py
```
