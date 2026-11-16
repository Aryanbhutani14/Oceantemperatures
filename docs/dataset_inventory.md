# Dataset inventory (Phase 0 audit)

All facts below come from the official catalogues, queried on 2026-11-16/17 by
the scripts in `scripts/audit/`. Raw responses are in `data/audit/`:

| File | Contents |
|---|---|
| `cmems_catalogue.json` | Copernicus Marine catalogue: variables, units, coordinates, depth levels |
| `grid_alignment.json` | Native grid vs canonical grid, chosen regridding operator, volume estimate |
| `argo_index_summary.json` | ARGO profiles in the domain for 2021 (from the GDAC index) |
| `podaac_catalogue.json` | NASA PO.DAAC (OSCAR, CCMP). The NASA CMR server timed out during the audit, so the facts below come from manual CMR queries. |

**Study period:** 2021-01-01 → 2021-12-31 (365 days, decision D-003).

**Canonical grid:** cell centres 5.00–30.00°N, 45.00–105.00°E, step 0.25° → 101 × 241 = 24,341 cells. Daily, UTC.

**Depths (m):** 0, 5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 300, 500, 700, 1000.

## 1. Inventory

| Dataset | Source / ID | Variables used | Native grid | Native time step | Coverage (catalogue) | Units: native → canonical | Role |
|---|---|---|---|---|---|---|---|
| GLORYS (ensemble member) | CMEMS `GLOBAL_MULTIYEAR_PHY_ENS_001_031` / `cmems_mod_glo_phy-all_my_0.25deg_P1D-m` (DOI 10.48670/moi-00024) | `thetao_glor` (potential temperature) | 0.25°, 75 depth levels | daily mean | 1993-01-01 → 2025-12-31 | °C → °C | **Target** |
| GLORYS12 monthly climatology | CMEMS `GLOBAL_MULTIYEAR_PHY_001_030` / `cmems_mod_glo_phy_my_0.083deg-climatology_P1M-m` (DOI 10.48670/moi-00021) | `thetao` | 1/12°, 50 levels | 12 monthly means (time axis labelled 2004) | multi-decade climatology | °C → °C | **Baseline / anomaly reference** (D-010) |
| OSTIA reprocessed L4 SST | CMEMS `SST_GLO_SST_L4_REP_OBSERVATIONS_010_011` / `METOFFICE-GLO-SST-L4-REP-OBS-SST` (DOI 10.48670/moi-00168) | `analysed_sst` | 0.05° | daily | 1981-10-01 → 2026-06-30 | **K → °C** (−273.15) | **Input** |
| Multi-obs SSS L4 (SMOS + SMAP + in situ) | CMEMS `MULTIOBS_GLO_PHY_S_SURFACE_MYNRT_015_013` / `cmems_obs-mob_glo_phy-sss_my_multi_P1D` (DOI 10.48670/moi-00051) | `sos` | 0.125° | daily | 1993-01-01 → 2024-12-15 | "1e-3" (practical salinity) → PSU | **Input** |
| DUACS L4 sea level (DT2024) | CMEMS `SEALEVEL_GLO_PHY_L4_MY_008_047` / `cmems_obs-sl_glo_phy-ssh_my_allsat-l4-duacs-0.125deg_P1D` (DOI 10.48670/moi-00148) | `sla`, `ugos`, `vgos` | 0.125° | daily | 1993-01-01 → 2026-05-15 | m, m s⁻¹ → same | **Input** (SLA + geostrophic currents, D-009) |
| CMEMS L4 winds (ASCAT + model) | CMEMS `WIND_GLO_PHY_L4_MY_012_006` / `cmems_obs-wind_glo_phy_my_l4_0.125deg_PT1H` (DOI 10.48670/moi-00185) | `eastward_wind`, `northward_wind` | 0.125° | **hourly** | 2007-01-11 → 2026-07-21 | m s⁻¹ → m s⁻¹ (24 h → daily mean) | **Input** (D-005) |
| ARGO core profiles | Argo GDAC (`data-argo.ifremer.fr`), global profile index | TEMP, PSAL, PRES + QC flags | point profiles | ~10-day float cycle | 2021 in domain: **4,071 profiles, 99 floats** (3,724 delayed-mode, 347 real-time); Arabian Sea 2,858, Bay of Bengal 1,024 | in-situ °C, dbar → potential temperature °C, m (GSW) | **Validation only** |
| OSCAR v2.0 final | NASA PO.DAAC `OSCAR_L4_OC_FINAL_V2.0` (DOI 10.5067/OSCAR-25F20) | u, v | 0.25° | daily | 1993-01-01 → 2026-01-16; ~31.7 MB per global daily file | m s⁻¹ | Optional input (needs Earthdata login) |
| CCMP v3.1 | NASA PO.DAAC `CCMP_WINDS_10M6HR_L4_V3.1` | uwnd, vwnd | 0.25° | 6-hourly | 1993-01-01 → 2026-09-30 (latest file) | m s⁻¹ | Optional input (needs Earthdata login) |
| GLORYS12 daily | CMEMS `GLOBAL_MULTIYEAR_PHY_001_030` / `..._0.083deg_P1D-m` | thetao | 1/12° | daily | 1993-01-01 → 2026-09-22 | °C | Not used (12 GB/year; the 0.25° member is enough) |
| IBTrACS | NOAA NCEI | cyclone tracks | points | 3-hourly | n/a | n/a | Auxiliary: event-based evaluation only, never a feature |

Every source we need **fully covers 2021**.

## 2. Grid alignment → regridding operator (computed, `grid_alignment.json`)

The canonical cell edges fall at x.125 / x.375 / x.625 / x.875°.

| Source | Native step | Native centre offset from canonical | Operator | Why |
|---|---|---|---|---|
| GLORYS 0.25° | 0.25° | (0, 0) | **exact selection** | Centres coincide, so no resampling is needed |
| GLORYS12 climatology | 1/12° | (0, 0) | **3×3 block mean** | 3×3 fine cells nest exactly inside each 0.25° cell |
| SSS, DUACS, winds | 0.125° | (0.0625, 0.0625) | **2×2 block mean** | Fine cell edges coincide with canonical edges, so a block mean is exactly area-conservative |
| OSTIA | 0.05° | (0.025, 0.025) | **area-weighted conservative** | 0.25 / 0.05 = 5, but the fine edges (multiples of 0.05) do **not** line up with canonical edges (x.125). A plain 5×5 block mean would shift the field by 0.025°, so overlap weights are used instead. |

## 3. Vertical: GLORYS 0.25° levels used

- **Levels kept:** 47 of the 75 native levels, down to 1045.85 m (the first level at or below 1000 m).
- **Interpolation:** each standard depth is linearly interpolated between its two bracketing native levels.
- **Depth 0 m:** uses the shallowest native level (0.506 m), with no extrapolation.
- **Seafloor:** cells shallower than a depth are NaN at that depth.

## 4. Download volume estimate (2021, bounding box + 0.5° pad, float32 uncompressed)

| Source | GB |
|---|---|
| GLORYS 0.25° (47 levels) | 1.77 |
| GLORYS12 climatology (12 months, 36 levels) | 0.40 |
| OSTIA | 0.93 |
| SSS | 0.15 |
| DUACS (3 variables) | 0.45 |
| CMEMS winds (hourly, 2 variables) | 7.16 |
| **Total** | **≈ 10.9 GB** (NetCDF compression will shrink this; D: has 105 GB free) |

## 5. Access

- **CMEMS:** one free Copernicus Marine account (`copernicusmarine login`) covers every source we need.
- **ARGO:** public, no login.
- **NASA PO.DAAC (OSCAR, CCMP):** needs a NASA Earthdata login, which is why both are optional.

## 6. Known caveats

- GLORYS assimilates satellite SST, altimetry and ARGO. ARGO is therefore independent of our **model and inputs**, but not of the training **target**.
- The multi-obs SSS product blends in-situ salinity, which includes ARGO's near-surface data.
- GLORYS `thetao` is **potential** temperature, while ARGO measures **in-situ** temperature. ARGO will be converted with TEOS-10 (GSW) before any comparison.
- Geostrophic currents (DUACS) miss the wind-driven Ekman component that OSCAR includes. The physics features use winds to stand in for it.
