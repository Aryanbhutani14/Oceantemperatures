// Builds reports/OceanEmbed_ML_Project_Report.docx following the BMU CSE2032 report template.
// All numbers come from the results JSON written by the pipeline.
// Run:  cd reports/build && node build_report.js
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell, WidthType, ShadingType,
  ImageRun, PageBreak, TableOfContents, Footer, PageNumber, LevelFormat, BorderStyle,
} = require("docx");

const ROOT = path.resolve(__dirname, "..", "..");
const J = (p) => JSON.parse(fs.readFileSync(path.join(ROOT, p), "utf8").replace(/\bNaN\b/g, "null"));
const IMG = (p) => path.join(__dirname, "img", p.replace("/", "_"));
const OUT = path.join(ROOT, "reports", "OceanEmbed_ML_Project_Report.docx");

const T5 = J("results/phase5/test_metrics.json"), CV5 = J("results/phase5/cv_selection.json"), FM = J("results/phase5/final_model.json");
const TCV = J("results/phase5/target_cv.json"), AB = J("results/phase5/ablation.json"), FT = J("results/phase6/full_test_metrics.json");
const AR = J("results/phase6/argo_validation.json"), IND = J("results/phase6/indicators.json"), TOL = J("results/phase6/tolerance_accuracy.json");
const AU = J("results/validation/audit.json");
const CL = J("results/phase7/classification.json"), RG = J("results/phase7/regularization.json"), FS = J("data/audit/features_summary.json");
const QC = J("data/audit/harmonisation_qc.json"), EDA = J("data/audit/eda_stats.json"), OUTL = J("data/audit/outlier_report.json");
const f2 = (x) => Number(x).toFixed(2), f3 = (x) => Number(x).toFixed(3), n0 = (x) => Number(x).toLocaleString("en-US");

const HEAD_FILL = "D9D9D9", NAVY = "000000", LIGHT = "F2F2F2", BORDER = "A6A6A6", H2C = "262626";
const CONTENT_W = 9026; // A4 with 1" margins, DXA
const TITLE = "OceanEmbed-ML: Reconstructing Subsurface Ocean Temperature of the North Indian Ocean from Satellite Surface Data using Machine Learning";

// ------------------------------------------------------------------ helpers
const runs = (parts, base = {}) => (Array.isArray(parts) ? parts : [parts]).map((p) =>
  typeof p === "string" ? new TextRun({ text: p, ...base }) : new TextRun({ ...base, ...p }));
const P = (parts, o = {}) => new Paragraph({ children: runs(parts, o.run || {}), spacing: { after: 120, line: 300 }, alignment: o.align || AlignmentType.JUSTIFIED, ...o.para });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)], pageBreakBefore: true });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const B = (parts, level = 0) => new Paragraph({ children: runs(parts), numbering: { reference: "bullets", level }, spacing: { after: 60, line: 288 } });
const N = (parts) => new Paragraph({ children: runs(parts), numbering: { reference: "steps", level: 0 }, spacing: { after: 60, line: 288 } });
const center = (parts, size, o = {}) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: o.after ?? 80 }, children: runs(parts, { size, font: o.font || "Cambria", bold: o.bold, italics: o.italics }) });
const brk = () => new Paragraph({ children: [new PageBreak()] });

function table(header, rows, widths, o = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  const scale = CONTENT_W / total;
  const w = widths.map((x) => Math.round(x * scale));
  w[w.length - 1] += CONTENT_W - w.reduce((a, b) => a + b, 0);
  const border = { style: BorderStyle.SINGLE, size: 4, color: BORDER };
  const borders = { top: border, bottom: border, left: border, right: border };
  const cell = (t, i, isHead, shade, bold) => new TableCell({
    width: { size: w[i], type: WidthType.DXA }, borders,
    shading: { type: ShadingType.CLEAR, color: "auto", fill: isHead ? HEAD_FILL : shade ? LIGHT : "FFFFFF" },
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    children: [new Paragraph({ spacing: { after: 0 }, children: runs(String(t), { size: o.size || 18, bold: isHead || bold, color: NAVY, font: "Calibri" }) })],
  });
  const hl = o.highlight || (() => false);
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: w,
    rows: [new TableRow({ tableHeader: true, children: header.map((h, i) => cell(h, i, true)) })].concat(
      rows.map((r, k) => new TableRow({ children: r.map((c, i) => cell(c, i, false, k % 2 === 1, hl(r, k))) }))),
  });
}
let figNo = 0, tabNo = 0;
const tcap = (t) => Object.assign(new Paragraph({ spacing: { before: 160, after: 80 }, keepNext: true, children: [new TextRun({ text: `Table ${++tabNo}: `, bold: true, size: 19, font: "Calibri" }), new TextRun({ text: t, size: 19, italics: true, font: "Calibri" })] }), { _isCaption: true });
function figure(file, widthIn, caption) {
  const b = fs.readFileSync(file);
  const pw = b.readUInt32BE(16), ph = b.readUInt32BE(20);
  const w = widthIn * 96, h = (w * ph) / pw;
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 40 }, keepNext: true, children: [new ImageRun({ type: "png", data: b, transformation: { width: Math.round(w), height: Math.round(h) }, altText: { title: caption, description: caption, name: path.basename(file) } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: `Figure ${++figNo}: `, bold: true, size: 19, font: "Calibri" }), new TextRun({ text: caption, size: 19, italics: true, font: "Calibri" })] }),
  ];
}

// ------------------------------------------------------------------ derived numbers
const climRmse = T5.models.climatology.overall.rmse;
const redPct = Math.round(100 * (1 - FT.overall.rmse / climRmse));
const gapClosed = Math.round(100 * (AR.overall.clim.rmse - AR.overall.pred.rmse) / (AR.overall.clim.rmse - AR.overall.glorys.rmse));
const lab = { final_gb_clim_feature: "Final: gradient boosting + climatology feature", gradient_boosting: "Gradient Boosting", random_forest: "Random Forest", bagging_trees: "Bagging (decision trees)", pca_regression: "PCA regression (8 modes) + boosting", svr_rbf: "SVR (RBF kernel)", knn: "KNN regression", ridge: "Ridge (L2)", lasso: "Lasso (L1)", linear_regression: "Linear Regression (OLS)", linear_gd_scratch: "Linear Regression (gradient descent, from scratch)", decision_tree: "Decision Tree", sst_only_linear: "SST-only linear (baseline)", climatology: "Climatology (baseline)", ensemble_avg: "Averaging ensemble GB+RF (not adopted)" };
const order = Object.keys(T5.models).sort((a, b) => T5.models[a].overall.rmse - T5.models[b].overall.rmse);
const fmtParams = (p) => (p && Object.keys(p).length ? Object.entries(p).map(([k, v]) => `${k}=${Array.isArray(v) ? v.join("+") : v}`).join(", ") : "—");

// ------------------------------------------------------------------ document body
const body = [];

// Cover page (template page 1)
body.push(
  new Paragraph({ spacing: { before: 1200 } }),
  center("Project Report", 28, { bold: true }), center("Machine Learning", 32, { bold: true }), center("CSE2032", 28, { bold: true, after: 600 }),
  center(TITLE, 30, { bold: true, after: 500 }),
  center("By", 26, { bold: true, italics: true, after: 300 }),
  ...[["Tanmay Sangwan", "240669"], ["Tanmay Kandwal", "240670"], ["Aryan Bhutani", "240406"], ["Prashast", "240586"]]
    .flatMap(([n, e]) => [center(n, 22, { bold: true, italics: true, after: 20 }), center(e, 22, { bold: true, italics: true, after: 200 })]),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200, after: 300 }, children: [new ImageRun({ type: "png", data: fs.readFileSync(IMG("bmu_logo.png")), transformation: { width: 115, height: 101 }, altText: { title: "BML Munjal University logo", description: "BML Munjal University logo", name: "logo" } })] }),
  center("Department of Computer Science and Engineering", 24, { bold: true, after: 20 }), center("School of Engineering and Technology", 24, { bold: true, after: 20 }),
  center("BML Munjal University", 24, { bold: true, after: 200 }), center("November 2026", 24, { bold: true }),
  brk(),
);

// Declaration (template page 2)
body.push(
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 }, children: [new TextRun({ text: "Declaration by the Candidates", bold: true, size: 32, font: "Cambria" })] }),
  new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 600, line: 420 }, children: [
    new TextRun("We hereby declare that the project entitled \""), new TextRun({ text: TITLE, bold: true, italics: true }),
    new TextRun("\" has been carried out to fulfil the partial requirements for completion of the course "), new TextRun({ text: "Machine Learning", bold: true }),
    new TextRun(" offered in the 5th Semester of the Bachelor of Technology (B.Tech) program in the Department of Computer Science and Engineering during AY-2026-27 (odd semester). This experimental work has been carried out by us and submitted to the course instructor. Due acknowledgments have been made in the text of the project to all other materials used. This project has been prepared in full compliance with the requirements and constraints of the prescribed curriculum."),
  ] }),
  ...["Tanmay Sangwan (240669)", "Tanmay Kandwal (240670)", "Aryan Bhutani (240406)", "Prashast (240586)"].map((t) => new Paragraph({ spacing: { after: 480 }, children: [new TextRun({ text: t, size: 22 })] })),
  new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text: "Place: ", bold: true }), new TextRun("BML Munjal University")] }),
  new Paragraph({ children: [new TextRun({ text: "Date: ", bold: true }), new TextRun("______ November, 2026")] }),
  brk(),
);

// Contents (template page 3)
body.push(
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 300 }, children: [new TextRun({ text: "Contents", bold: true, size: 32, font: "Cambria" })] }),
  new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-1" }),
);

// ---------------- 1. Introduction
body.push(H1("1. Introduction"),
  P("Satellites measure the ocean surface every day: its temperature, salinity, height and the winds and currents acting on it. What happens below the surface, however, is just as important. The depth and warmth of the upper-ocean layer control how much heat is available to tropical cyclones, how the Indian monsoon develops, where fish aggregate and how the ocean stores heat in a warming climate. Direct subsurface measurements are sparse: in 2021 there were only about 4,000 ARGO float profiles in the whole North Indian Ocean, against millions of satellite pixels."),
  P("In this CSE2032 course project we reconstruct the vertical temperature structure of the North Indian Ocean (5–30°N, 45–105°E) at 15 standard depths from 0 to 1000 m, daily on a 0.25° grid, using only surface satellite observations. The problem is aligned with a problem statement published by the Indian National Centre for Ocean Information Services (INCOIS), Ministry of Earth Sciences. We apply the methods of the course (regression, regularization, classification, ensembles, PCA, cross-validation and model evaluation) to this real geoscience problem, with particular attention to realistic, leakage-free evaluation."),
  P(["Our contributions are: (i) a reproducible pipeline that harmonises eight datasets onto one common grid; (ii) exploratory analysis and 40 physically motivated features; (iii) a fair, leakage-free comparison of 13 regression models and 7 classifiers from the course syllabus, including a linear regression trained by gradient descent implemented from scratch; (iv) a final model reaching a test RMSE of ", { text: `${f2(FT.overall.rmse)} °C`, bold: true }, ` (${redPct}% below the climatology baseline) and `, { text: `${f2(AR.overall.pred.rmse)} °C against independent ARGO floats`, bold: true }, "; and (v) a cyclone-favourability classifier and oceanographic indicators relevant to disaster management."]),
);

// ---------------- 2. Problem statement
body.push(H1("2. Problem Statement"),
  H2("2.1 Problem background"),
  P("The INCOIS problem statement this project is aligned with asks for a system that estimates three-dimensional ocean temperature from surface satellite data: harmonise multi-source data to a daily 0.25° grid; use sea surface temperature (SST), sea surface salinity (SSS), sea surface height / sea level anomaly (SLA), surface currents and surface winds as inputs; train on GLORYS reanalysis temperature; and validate against independent ARGO observations using correlation, RMSE and bias, with a proof of concept over the Bay of Bengal and the Arabian Sea."),
  table(["Item", "Specification"], [
    ["Region", "North Indian Ocean, 5°N–30°N, 45°E–105°E"],
    ["Grid / time step", "0.25° × 0.25° (101 × 241 cell centres), daily"],
    ["Output depths (m)", "0, 5, 10, 20, 30, 50, 75, 100, 125, 150, 200, 300, 500, 700, 1000"],
    ["Inputs", "SST, SSS, SSH/SLA, surface currents (U, V), 10 m winds (U, V)"],
    ["Training target", "GLORYS ocean reanalysis temperature"],
    ["Validation", "Independent ARGO float profiles (correlation, RMSE, bias)"],
  ], [1, 3]),
  tcap("Problem specification used in this project."),
  H2("2.2 Our formulation"),
  B([{ text: "Regression (main task): ", bold: true }, "for every ocean grid cell and day, predict the temperature at the 15 depths from the surface features of that cell and its neighbourhood."]),
  B([{ text: "Classification (added for the course): ", bold: true }, "predict whether the ocean is favourable for cyclone intensification, defined as Tropical Cyclone Heat Potential TCHP ≥ 60 kJ cm⁻² (Leipper & Volgenau 1972). This turns the reconstruction into an actionable yes/no decision."]),
  H2("2.3 Scope and constraints"),
  B("Models and evaluation methods are taken from the CSE2032 syllabus (Section 5.12 maps every method to a syllabus topic)."),
  B("One year of data (2021) because of the submission deadline. 2021 contains five cyclones (Tauktae, Yaas, Gulab, Shaheen, Jawad) and 4,071 ARGO profiles in the region."),
  B("No data leakage: whole months are held out for testing (never random rows), and every modelling decision is made by cross-validation on training months only."),
);

// ---------------- 3. Dataset
body.push(H1("3. Dataset Description"),
  P(`We combine eight public datasets. All gridded products were downloaded from Copernicus Marine for 2021, subset on the server to the study region plus a 0.5° margin (about 6.8 GB in total), and harmonised onto one canonical grid: 11,880 ocean cells × 365 days, with the target at 15 depths.`),
  table(["Dataset (product)", "Variables", "Native resolution", "Role"], [
    ["GLORYS reanalysis 0.25° (GLOBAL_MULTIYEAR_PHY_ENS_001_031)", "Potential temperature, 75 levels", "0.25°, daily", "Target"],
    ["GLORYS12 climatology (GLOBAL_MULTIYEAR_PHY_001_030)", "Monthly mean temperature", "1/12°, monthly", "Baseline and feature"],
    ["OSTIA L4 (SST_GLO_SST_L4_REP_OBSERVATIONS_010_011)", "SST (K → °C)", "0.05°, daily", "Input"],
    ["Multi-obs SSS L4, SMOS+SMAP (MULTIOBS_GLO_PHY_S_SURFACE_MYNRT_015_013)", "SSS (PSU)", "0.125°, daily", "Input"],
    ["DUACS L4 (SEALEVEL_GLO_PHY_L4_MY_008_047)", "SLA, geostrophic U/V", "0.125°, daily", "Input"],
    ["ASCAT-based L4 winds (WIND_GLO_PHY_L4_MY_012_006)", "10 m wind U/V", "0.125°, hourly", "Input"],
    ["ARGO GDAC core profiles", "Temperature, salinity, pressure", "Point profiles", "Independent validation"],
    ["IBTrACS North Indian", "Cyclone tracks", "3-hourly points", "Event analysis only"],
  ], [3.2, 2, 1.4, 1.4]),
  tcap("Source datasets."),
  P(`The final machine-learning table has ${n0(FS.tables.train.rows + FS.tables.test.rows)} rows (one per ocean cell-day; train ${n0(FS.tables.train.rows)}, test ${n0(FS.tables.test.rows)}) and ${FS.tables.train.columns} columns. Table 3 lists the features and targets with their data types.`),
  table(["Variable", "Description (unit)", "Data type", "Role"], [
    ["sst", "Sea surface temperature (°C)", "float32", "Feature"],
    ["sss", "Sea surface salinity (PSU)", "float32", "Feature"],
    ["sla", "Sea level anomaly (m)", "float32", "Feature"],
    ["uo, vo", "Surface geostrophic current (m s⁻¹)", "float32", "Feature"],
    ["u10, v10", "10 m wind (m s⁻¹)", "float32", "Feature"],
    ["33 derived features", "Wind speed, current speed, wind stress, curl, Ekman pumping, SST/SLA gradients, SLA Laplacian, 5×5 neighbourhood means, 7-day trailing means and changes, SST anomaly, lat, lon, sin/cos of day of year, bottom depth, 8 PCA embedding components", "float32", "Feature"],
    ["clim_d00 … clim_d14", "External climatology at each depth (°C)", "float32", "Feature"],
    ["y_d00 … y_d14", "GLORYS temperature at 0 … 1000 m (°C)", "float32", "Target (regression)"],
    ["a_d00 … a_d14", "Anomaly = y − climatology (°C)", "float32", "Intermediate target"],
    ["label", "1 if TCHP ≥ 60 kJ cm⁻², else 0", "int8", "Target (classification)"],
    ["time, cell_id, lat_idx, lon_idx, month, split, region", "Keys and grouping variables", "datetime64, int32, int16, int8, category", "Metadata"],
  ], [1.6, 3.6, 1.2, 1.2]),
  tcap("Features and targets in the ML table."),
);

// ---------------- 4. Literature review
body.push(H1("4. Literature Review"),
  P("Estimating subsurface temperature from surface observations has been studied for four decades. The studies below use the same kind of data as this project: satellite sea surface temperature, sea surface height (or sea level anomaly) and salinity, sometimes with winds, as inputs, and in-situ profiles (XBT, CTD, ARGO) or reanalysis as ground truth. They range from physical-statistical relations and regression to support vector machines and tree ensembles."),
  table(["Study", "Data", "Method", "Region / depth", "Finding and relevance to this project"], [
    ["Rebert et al. (1985), J. Geophys. Res.", "Tide-gauge sea level, XBT profiles", "Statistical regression (sea level vs thermocline)", "Tropical Pacific, upper ocean", "Sea level tracks thermocline depth and heat content: the physical basis for using SLA as our main subsurface predictor"],
    ["Shay, Goni & Black (2000), Mon. Weather Rev.", "Altimetry, in-situ profiles", "Heat content above the 26 °C isotherm (TCHP)", "Gulf of Mexico, Hurricane Opal", "Warm subsurface features fuel cyclone intensification: motivates our TCHP indicator and classification task"],
    ["Ali, Swain & Weller (2004), Geophys. Res. Lett.", "SST, SSH, wind stress, heat fluxes; mooring profiles", "Artificial neural network", "Arabian Sea, upper ocean", "Surface parameters reproduce Arabian Sea thermal structure (average RMS error about 0.58 °C)"],
    ["Buongiorno Nardelli & Santoleri (2005), J. Atmos. Oceanic Technol.", "Surface fields + historical CTD profiles", "Multivariate EOF (PCA) reconstruction", "North Pacific (HOT station)", "A few vertical modes explain most profile variance: the idea behind our PCA regression"],
    ["Guinehut et al. (2012), Ocean Science (ARMOR3D)", "Satellite SST and SLA plus ARGO", "Multiple linear regression + optimal interpolation", "Global, 0–1500 m", "Operational statistical product: linear regression is a strong baseline"],
    ["Nagamani et al. (2012), Remote Sens. Lett.", "Satellite SST and SSH; in-situ profiles", "Regression-based TCHP from altimetry", "North Indian Ocean", "Satellite TCHP is skilful against in-situ data (R² ≈ 0.65 daily): our region and indicator"],
    ["Su, Wu, Yan & Kidwell (2015), Remote Sens. Environ.", "SST, SSH, SSS anomalies; ARGO", "Support vector regression", "Indian Ocean, 0–1000 m", "Adding salinity reduced MSE by about 12%: we include SSS and compare SVR"],
    ["Su, Li & Yan (2018), J. Geophys. Res. Oceans", "SSH, SST, SSS, wind anomalies; ARGO", "Random forest", "Global, to 1000 m and deeper", "Tree ensembles retrieve subsurface anomalies well: we compare random forest"],
    ["Su, Yang, Lu & Yan (2019), Remote Sensing", "Satellite surface fields; ARGO", "Gradient boosting (XGBoost vs GBDT)", "Global, 0–2000 m", "Boosted trees outperform plain GBDT: we compare gradient boosting"],
    ["Qi et al. (2022), Remote Sensing", "Satellite surface data; ARGO", "Stacking ensemble of XGBoost, random forest and LightGBM", "South China Sea", "Ensembles of tree models improve accuracy: supports our ensemble comparison"],
  ], [1.55, 1.45, 1.35, 1.2, 2.45]),
  tcap("Related work using the same kind of data."),
  P("Four lessons shaped our design. First, sea level is the most informative input for the thermocline, because a deeper warm layer raises the sea surface (Rebert et al. 1985). Second, salinity matters in the Indian Ocean, where river runoff and evaporation create strong contrasts (Su et al. 2015). Third, regression, support vector machines and tree ensembles are established, competitive approaches, and boosting and stacking of trees tend to give the best accuracy (Su et al. 2018, 2019; Qi et al. 2022). Fourth, the heat content above the 26 °C isotherm is a validated, decision-relevant quantity for cyclones in this very region (Shay et al. 2000; Nagamani et al. 2012). Our project brings these ideas together in one leakage-free comparison of course-syllabus models for the North Indian Ocean, and adds an independent ARGO validation and a cyclone-favourability classifier."),
);

// ---------------- 5. Methodology
body.push(H1("5. Methodology"),
  H2("5.1 Pipeline overview"),
  N("Audit: query the official catalogues for every dataset (variables, units, grid, coverage) before downloading."),
  N("Acquisition: download month by month with server-side subsetting; verify every file and record SHA-256 checksums."),
  N("Harmonisation: one conservative (area-weighted) regridding operator for all sources, explicit unit conversions, daily averaging, ocean masking."),
  N("Integration and EDA: join all sources onto one data cube with an exact-coordinate join; explore distributions, patterns and data issues."),
  N("Feature engineering: compute 40 features on the grid, then flatten into one row per ocean cell-day."),
  N("Modelling: baselines, 11 regression models and 7 classifiers; hyperparameters tuned with month-grouped cross-validation."),
  N("Evaluation: identical test rows for every model; per-depth, regional and seasonal breakdowns; independent ARGO validation; ocean indicators."),
  H2("5.2 Data preprocessing and harmonisation"),
  P("Each dataset is renamed to canonical variable names; units are converted explicitly (for example OSTIA from kelvin to °C) only after checking the file's unit attribute; coordinates are sorted; and the data are regridded with the operator below. Hourly winds are averaged to daily values (all 24 hours required). Satellite gaps are never filled; they stay as missing values."),
  table(["Source", "Native grid vs ours", "Operator"], [
    ["GLORYS 0.25°", "Same cell centres", "Identity (exact selection) + linear interpolation to 15 depths"],
    ["GLORYS12 climatology", "1/12°, nested 3×3", "Exact 3×3 block mean"],
    ["SSS, SLA, winds", "0.125°, nested 2×2", "Exact 2×2 block mean"],
    ["OSTIA", "0.05°, edges not aligned", "Area-weighted conservative regridding (partial cells)"],
  ], [1.6, 2, 3]),
  tcap("Regridding operator per source (all one tested function)."),
  P(`Quality control removes only physically impossible values. A first version with a 35 °C limit deleted real Persian Gulf summer temperatures (up to 36.7 °C), so the limit was raised to 38 °C and no values were removed. The ocean mask has ${n0(QC.glorys.masks.n_ocean_cells)} cells; it also removes Tibetan lakes present in OSTIA and land values present in the gap-filled winds. Six unit tests check the regridding (identity, exact block mean, area conservation, missing-value rule).`),
  H2("5.3 Exploratory data analysis"),
  P(`The EDA used all days for descriptive statistics but only training days for relationship analyses (correlations, PCA), so the test months never influenced feature choices. Key findings:`),
  B([{ text: "Hardest layer: ", bold: true }, `the temperature anomaly (truth minus climatology) has a standard deviation of ${f2(EDA.anomaly_std_by_depth["100"])} °C at 100 m but only ${f2(EDA.anomaly_std_by_depth["1000"])} °C at 1000 m, so the thermocline (75–150 m) is the hardest layer.`]),
  B([{ text: "Sea level tracks the thermocline: ", bold: true }, `Spearman correlation between SLA and temperature at 100 m is ${f2(EDA.feature_target_spearman_train.absolute.sla["100"])}.`]),
  B([{ text: "SST only matters near the surface: ", bold: true }, `correlation ${f2(EDA.feature_target_spearman_train.absolute.sst["0"])} at 0 m, falling to about zero by 125 m.`]),
  B([{ text: "Regional contrast: ", bold: true }, "the Bay of Bengal is warmer and fresher at the surface but 1.5–2 °C colder below 150 m than the Arabian Sea."]),
  B([{ text: "Low-dimensional profiles: ", bold: true }, `${EDA.pca_anomaly_profiles_train.n_components_90pct} principal components explain 90% of the variance of the 15-depth anomaly profiles.`]),
  B([{ text: "Outliers are real events: ", bold: true }, `SST values flagged by a robust z-score are ${f2(OUTL.variables.sst.frac_flags_near_cyclone_300km_7d / OUTL.random_ocean_value_frac_near_cyclone)}× more likely to lie within 300 km and 7 days of a 2021 cyclone track than a random ocean value. They are cyclone cold wakes, so they were kept.`]),
  ...figure(IMG("phase3/09_feature_target_corr_by_depth.png"), 6.3, "Spearman correlation of each feature with temperature (left) and with the anomaly (right) at each depth, training days only."),
  ...figure(IMG("phase3/07_profiles_region_season_variance.png"), 6.3, "Mean profiles by region and season, and the variability left to learn after removing the climatology."),
  H2("5.4 Feature engineering"),
  P("Features are computed on the grid first, so that spatial features can use neighbouring cells, and then flattened. Each group answers an EDA finding."),
  table(["Group", "Features", "Reason"], [
    ["Direct (7)", "sst, sss, sla, uo, vo, u10, v10", "Problem-statement inputs"],
    ["Kinematic (2)", "wind speed, current speed", "Mixing and advection strength"],
    ["Wind forcing (4)", "wind stress τx, τy (Large & Pond), stress curl, Ekman pumping", "Upwelling lifts the thermocline"],
    ["Gradients (5)", "|∇SST|, ∂SLA/∂x, ∂SLA/∂y, |∇SLA|, ∇²SLA", "Fronts, geostrophic slope, eddies"],
    ["Neighbourhood (3)", "5×5 means of SLA, SST, SSS", "Spatial context"],
    ["Temporal (5)", "7-day trailing means and 7-day changes", "Ocean memory (past days only)"],
    ["Anomaly (1)", "SST minus climatology", "Correlation 0.75 vs 0.26 for raw SST"],
    ["Geographic, seasonal, static (5)", "lat, lon, sin/cos day of year, bottom depth", "Regime, season, shelf vs open ocean"],
    ["Embedding (8)", "PCA of standardised 3×3×7 surface patches (fit on train)", "Compact PCA summary of the local surface pattern; 95% of patch variance"],
    ["Per depth", "Climatology at that depth", "Chosen by cross-validation (Section 7.4)"],
  ], [1.5, 3.2, 2.3]),
  tcap("Engineered features."),
  H2("5.5 Train/test split and leakage control"),
  P("Ocean data are strongly autocorrelated: neighbouring days and cells are near-duplicates, so a random row split would leak information and inflate the scores. We therefore hold out whole months: February, May, August and November (one per season) form the test set, the other eight months form the training set, and the seven days on either side of each test month are discarded as buffers (189 train days, 120 test days, 56 buffer days). Temporal features use past days only, the PCA embedding is fitted on training days only, and the climatology is an external multi-decade product. Automated tests (tests/test_features.py) check that temporal features never use future days and that the train and test tables never share, or come within 7 days of, a day."),
  H2("5.6 Baseline models"),
  B([{ text: "Climatology: ", bold: true }, "the long-term average profile for the month and location. It is what is available without any 2021 data, and all skill scores are measured against it (skill = 1 − MSE/MSE of climatology)."]),
  B([{ text: "SST-only linear regression: ", bold: true }, "tests whether surface temperature alone is enough."]),
  B([{ text: "Classification baselines: ", bold: true }, "majority class, and the climatology rule (predict favourable if the climatological TCHP ≥ 60)."]),
  H2("5.7 Models compared"),
  table(["Model", "Why it is included"], [
    ["Linear Regression (OLS) and gradient descent from scratch", "Interpretable reference; our NumPy mini-batch gradient descent (cost J = MSE/2) is verified against the closed-form OLS solution"],
    ["Ridge (L2), Lasso (L1)", "Handle multicollinearity among related features; Lasso performs feature selection"],
    ["KNN regression", "Analogue method: similar surface states give similar profiles; implemented to handle missing deep levels"],
    ["SVR with RBF kernel", "Nonlinear kernel method used in earlier work (Su et al. 2015)"],
    ["Decision Tree", "Nonlinear thresholds; high variance on its own"],
    ["PCA regression", "Predicts 8 vertical principal-component scores, so whole profiles stay consistent"],
    ["Logistic Regression (L1, L2), SVM, Decision Tree, KNN", "Classification of cyclone-favourable ocean"],
  ], [2.4, 4.6]),
  tcap("Models compared and the reason for each."),
  H2("5.8 Ensemble techniques"),
  B([{ text: "Bagging: ", bold: true }, "30 deep trees on bootstrap samples; averaging reduces variance."]),
  B([{ text: "Random Forest: ", bold: true }, "bagging plus random feature subsets, which decorrelates the trees."]),
  B([{ text: "Gradient Boosting: ", bold: true }, "shallow trees fitted sequentially to residuals with a small learning rate (histogram-based implementation)."]),
  B([{ text: "Averaging ensemble: ", bold: true }, "average of the two best models; adopted only if it improves the cross-validated error by at least 1%, so complexity is never added for presentation."]),
  H2("5.9 Hyperparameter tuning and cross-validation"),
  P("Every hyperparameter grid is evaluated with GroupKFold (4 folds) where the groups are calendar months, so each fold holds out two whole training months. Regression models are scored by the mean anomaly RMSE at five representative depths (0, 50, 100, 300, 1000 m); classifiers by ROC-AUC (GridSearchCV). Preprocessing (median imputation, standardisation) is inside each scikit-learn pipeline, so it is refitted on the training folds only. The test months are used once, for final scoring, on identical rows for every model."),
  H2("5.10 Regularization"),
  P("Regularization appears at several levels: L2 and L1 penalties (Ridge, Lasso, logistic regression with C = 1/λ), tree depth and leaf-size limits, and the learning rate and L2 penalty of gradient boosting. Section 7.6 shows validation curves in which overfitting appears and is then controlled."),
  H2("5.11 Evaluation metrics"),
  P("Regression: RMSE, MAE, bias, R², Pearson r and skill versus climatology, per depth and pooled, plus the share of predictions within ±0.5 °C and ±1 °C. Classification: accuracy, precision, recall, F1, ROC-AUC, specificity and confusion matrices. Because R² on absolute temperature is inflated by the large vertical temperature range (even climatology scores 0.98), we use RMSE and skill as the headline metrics. Uncertainty of the headline numbers is estimated with a block bootstrap over test days."),
  H2("5.12 Alignment with the CSE2032 syllabus"),
  P("Every modelling and evaluation method maps to a topic of the course handout. The few additions beyond the handout are standard extensions needed to treat this data correctly, and the reason for each is given."),
  table(["Method used in this project", "CSE2032 handout topic", "Status / reason"], [
    ["Linear regression; cost function; gradient descent implemented from scratch", "Regression; cost function and gradient descent", "In syllabus"],
    ["Ridge (L2), Lasso (L1); validation curves; bias–variance", "Regularization; under/overfitting, bias–variance trade-off", "In syllabus"],
    ["Logistic regression (L1/L2), SVM, decision tree, KNN", "Classification", "In syllabus"],
    ["Bagging, random forest, gradient boosting, averaging ensemble", "Ensemble: decision forest, bagging, boosting", "In syllabus"],
    ["PCA regression; PCA summary of surface patterns", "Dimension reduction with PCA", "In syllabus"],
    ["GroupKFold cross-validation, GridSearchCV, hyperparameter grids", "Cross-validation, hyperparameter tuning", "In syllabus; grouping by month is required because neighbouring days are near-duplicates (random K-fold would leak)"],
    ["Accuracy, precision, recall, F1, confusion matrix, ROC/AUC, R², bootstrap confidence intervals", "Model validation and selection", "In syllabus"],
    ["Outlier screening with a robust z-score", "Anomaly detection (density estimation)", "In syllabus: a z-score threshold is a Gaussian density threshold"],
    ["SVR and KNN regression", "SVM and KNN (taught for classification)", "Extension: the same algorithms applied to a regression target"],
    ["Regridding, unit conversion, ARGO collocation, oceanographic indicators (D20, TCHP)", "Data import, processing and transformation (course overview)", "Domain-specific data preparation needed to build a valid dataset; not a modelling method"],
    ["Permutation importance, ablation study", "Model interpretation and selection", "Small extension used only to explain results"],
  ], [2.6, 2.2, 2.2]),
  tcap("Methods used and the corresponding CSE2032 syllabus topics."),
);

// ---------------- 6. Technology stack
body.push(H1("6. Technology Stack"),
  table(["Layer", "Tools"], [
    ["Language and packaging", "Python 3.13; installable package src/oceanembed_ml (pyproject.toml); thin command-line scripts per phase"],
    ["Data access", "copernicusmarine toolbox (CMEMS), NASA CMR, Argo GDAC index, requests"],
    ["Scientific data", "xarray, NetCDF4, NumPy, SciPy, pandas, PyArrow / Parquet"],
    ["Oceanography", "gsw (TEOS-10) for ARGO pressure-to-depth and potential temperature"],
    ["Machine learning", "scikit-learn: LinearRegression, Ridge, Lasso, LogisticRegression, SVR/SVC, KNN, DecisionTree, RandomForest, Bagging, HistGradientBoosting, PCA, GroupKFold, GridSearchCV, validation_curve; custom NumPy gradient descent"],
    ["Visualisation", "matplotlib; executed Jupyter notebooks (nbformat, nbclient)"],
    ["Quality", "pytest (21 tests), Git/GitHub version control, decision log"],
    ["Reporting", "Node.js pptxgenjs and docx for the presentation and this report (numbers read from result files)"],
  ], [1.8, 5.2]),
  tcap("Technology stack."),
);

// ---------------- 7. Experimental results
const cvRows = ["linear_gd_scratch", "ridge", "lasso", "knn", "svr_rbf", "decision_tree", "bagging_trees", "random_forest", "gradient_boosting", "pca_regression"].map((n) =>
  [lab[n], fmtParams(CV5[n].best_params), f3(CV5[n].best_cv_rmse), f3(CV5[n].best_cv_fold_std)]);
body.push(H1("7. Experimental Results"),
  H2("7.1 Cross-validation and hyperparameter tuning"),
  table(["Model", "Selected hyperparameters", "CV RMSE (°C)", "Fold std"], cvRows, [2.6, 2.4, 1, 1]),
  tcap("Hyperparameters chosen by GroupKFold-by-month cross-validation (anomaly RMSE, train months only)."),
  P(`The averaging ensemble of gradient boosting and random forest reached a CV RMSE of ${f3(CV5.ensemble_avg.best_cv_rmse)} against ${f3(CV5.ensemble_avg.best_single_cv_rmse)} for boosting alone, a gain of only ${(100 * CV5.ensemble_avg.relative_gain).toFixed(3)}%, below the 1% adoption rule. It was therefore not adopted, and gradient boosting was selected.`),
  H2("7.2 Regression results on the test months"),
  table(["Model", "RMSE °C", "MAE °C", "Bias °C", "Skill", "RMSE 100 m", "R² 100 m"], order.map((n) => {
    const m = T5.models[n];
    return [lab[n] || n, f3(m.overall.rmse), f3(m.overall.mae), f3(m.overall.bias), f2(m.mean_skill_over_depths), f2(m.per_depth["100"].rmse), f2(m.per_depth["100"].r2)];
  }), [3, 0.9, 0.9, 0.9, 0.8, 0.7, 1], { highlight: (r) => r[0].startsWith("Final") }),
  tcap(`All models scored on the same ${n0(T5.eval_subset.rows)} test rows (absolute temperature, sorted by RMSE). R² is shown at 100 m because R² pooled over all depths is inflated by the large vertical temperature range.`),
  P(`Every model beats the climatology. Tree ensembles are the strongest family: a single decision tree reaches ${f3(T5.models.decision_tree.overall.rmse)} °C while a random forest reaches ${f3(T5.models.random_forest.overall.rmse)} °C, a clear illustration of variance reduction by averaging. Ridge, Lasso and OLS are almost identical because 400,000 training rows strongly constrain 40 coefficients, so there is little to regularise. The from-scratch gradient-descent model matches the closed-form solution (${f3(T5.models.linear_gd_scratch.overall.rmse)} vs ${f3(T5.models.linear_regression.overall.rmse)} °C). SVR is accurate but needed about ${Math.round(T5.models.svr_rbf.predict_seconds_200k / 60)} minutes to predict 200,000 rows, against ${Math.round(T5.models.gradient_boosting.predict_seconds_200k)} seconds for boosting.`),
  ...figure(IMG("phase5/01_rmse_skill_by_depth.png"), 6.3, "RMSE (left) and skill versus climatology (right) by depth for all models, test months."),
  H2("7.3 Final model: accuracy by depth"),
  table(["Depth (m)", "0", "10", "30", "50", "75", "100", "150", "200", "300", "500", "1000"],
    [["RMSE °C", ...["0", "10", "30", "50", "75", "100", "150", "200", "300", "500", "1000"].map((d) => f2(FT.per_depth[d].rmse))],
     ["Skill", ...["0", "10", "30", "50", "75", "100", "150", "200", "300", "500", "1000"].map((d) => f2(FT.per_depth[d].skill_vs_clim))],
     ["Within ±1 °C (%)", ...["0", "10", "30", "50", "75", "100", "150", "200", "300", "500", "1000"].map((d) => TOL.per_depth_within_1C[d].model_pct.toFixed(0))]],
    [1.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6]),
  tcap(`Final model on all ${n0(FT.rows)} test cell-days.`),
  P(`On the full test set the final model reaches RMSE ${f3(FT.overall.rmse)} °C (climatology ${f3(climRmse)} °C) with a mean skill of ${f2(FT.mean_skill_over_depths)}. ${TOL.overall["1.0"].model_pct.toFixed(1)}% of all ${n0(TOL.n_values)} predicted values are within ±1 °C of the truth (climatology ${TOL.overall["1.0"].clim_pct.toFixed(1)}%) and ${TOL.overall["0.5"].model_pct.toFixed(1)}% within ±0.5 °C (climatology ${TOL.overall["0.5"].clim_pct.toFixed(1)}%). The error peaks in the thermocline, exactly where the EDA located the largest unexplained variance.`),
  ...figure(IMG("phase6/01_map_T100_tauktae.png"), 6.4, "Temperature at 100 m on 15 May 2021 during cyclone Tauktae: GLORYS truth, ML prediction from surface data only, and error."),
  H2("7.4 Target formulation chosen by cross-validation"),
  P(`An ablation on the test months suggested that predicting the anomaly might not be optimal. Because test results must not drive decisions, the question was re-asked with the same month-grouped CV on the training months: anomaly target ${f3(TCV.variants.anomaly.cv_rmse_mean)} °C, absolute target ${f3(TCV.variants.absolute.cv_rmse_mean)} °C, and anomaly with the climatology as an input feature ${f3(TCV.variants["anomaly+clim_feat"].cv_rmse_mean)} °C. The last formulation was adopted. The external climatology is itself biased for 2021 (−0.32 °C); given as a feature, the model learns when to trust it. The final model improves the test RMSE from ${f3(T5.models.gradient_boosting.overall.rmse)} to ${f3(FM.overall.rmse)} °C.`),
  H2("7.5 Ablation study"),
  table(["Feature set (gradient boosting)", "Test RMSE °C", "Skill"], Object.entries(AB.features).map(([k, v]) => [k, f3(v.overall_rmse), f2(v.mean_skill)]), [4, 1.5, 1.5]),
  tcap("Feature-group ablation."),
  P(`Engineered features raise the skill from ${f2(AB.features["direct_only (7 raw inputs)"].mean_skill)} (raw inputs only) to ${f2(AB.features["all (40)"].mean_skill)}. Removing latitude/longitude causes the largest loss, which shows the model partly learns regional regimes (a limitation for unseen regions). Wind-forcing, gradient and embedding features add little for boosting, which reconstructs that information from the raw fields, although the linear models rely on the embedding in the thermocline. The learning curve saturates: ${f3(AB.data_size["25000"].overall_rmse)} °C with 25k rows, ${f3(AB.data_size["100000"].overall_rmse)} with 100k and ${f3(AB.data_size["400000"].overall_rmse)} with 400k.`),
  ...figure(IMG("phase5/09_ablation.png"), 6.4, "Ablations: feature groups (left), target formulation (centre), learning curve (right)."),
  H2("7.6 Regularization"),
  table(["Experiment", "Without / weak regularization", "With tuned regularization"], [
    ["Ridge (L2), 861 polynomial features on 2,000 rows", `train RMSE ${f2(RG.ridge_poly.unregularised_train_rmse)}, CV RMSE ${f2(RG.ridge_poly.unregularised_cv_rmse)} °C (overfitting)`, `α ≈ ${Math.round(RG.ridge_poly.best_alpha)}: CV RMSE ${f2(RG.ridge_poly.best_cv_rmse)} °C`],
    ["Lasso (L1), same model", `${RG.lasso_poly.nonzero_coefs[0]} non-zero coefficients, CV ${f2(RG.lasso_poly.cv_rmse[0])} °C`, `α = 0.1: ${RG.lasso_poly.nonzero_coefs[6]} of 861 features kept, CV ${f2(RG.lasso_poly.cv_rmse[6])} °C`],
    ["Decision-tree depth (classification)", `depth 30: train acc ${f2(RG.tree_depth.train_acc[10])}, CV ${f3(RG.tree_depth.cv_acc[10])}`, `depth ${RG.tree_depth.best_depth}: CV ${f3(Math.max(...RG.tree_depth.cv_acc))}`],
    ["Logistic regression C = 1/λ", `C = 1e-5 (too strong): CV AUC ${f3(RG.logistic_C.cv_auc[0])}`, `C ≈ 0.01–1: CV AUC ${f3(Math.max(...RG.logistic_C.cv_auc))}`],
    ["Boosting learning rate", `0.3: CV error rises after 25 trees`, `0.05: CV keeps improving to 400 trees`],
  ], [2.4, 2.6, 2]),
  tcap("Regularization experiments (GroupKFold-by-month validation curves)."),
  ...figure(IMG("phase7/04_regularization_curves.png"), 6.5, "Validation curves: training vs cross-validation error for Ridge, Lasso, tree depth, logistic C and boosting shrinkage."),
  H2("7.7 Classification: cyclone-favourable ocean"),
  P(`The label is 1 when TCHP ≥ 60 kJ cm⁻² (${Math.round(100 * CL.positive_rate.test_eval)}% of test rows, a balanced problem). Inputs are the 40 features plus the climatological TCHP. Models were tuned with GridSearchCV (ROC-AUC, GroupKFold by month) and evaluated on the same ${n0(CL.n_rows.test_eval)} test rows.`),
  table(["Model", "Best hyperparameters", "CV AUC", "Accuracy", "Precision", "Recall", "F1", "ROC-AUC"],
    ["majority_class", "climatology_rule", "decision_tree", "knn", "logistic_l2", "logistic_l1", "svm_rbf", "random_forest", "gradient_boosting"].map((n) => {
      const m = CL.models[n], v = (x) => (x == null ? "—" : f3(x));
      return [{ majority_class: "Majority class", climatology_rule: "Climatology rule", decision_tree: "Decision Tree", knn: "KNN", logistic_l2: "Logistic Regression (L2)", logistic_l1: "Logistic Regression (L1)", svm_rbf: "SVM (RBF)", random_forest: "Random Forest", gradient_boosting: "Gradient Boosting" }[n],
        fmtParams(m.best_params), v(m.cv_auc), v(m.accuracy), v(m.precision), v(m.recall), v(m.f1), v(m.roc_auc)];
    }), [1.8, 1.9, 0.7, 0.75, 0.75, 0.7, 0.6, 0.75]),
  tcap("Classification results on the test months."),
  P(`Logistic regression with L1 regularisation has the best cross-validated AUC and was selected; gradient boosting is about one percentage point more accurate on test (${f3(CL.models.gradient_boosting.accuracy)}). The climatology rule has high precision but misses one third of the favourable areas (recall ${f2(CL.models.climatology_rule.recall)}), while every ML model catches about 93–94%. For a cyclone warning, a missed favourable area is the costly error. The high accuracy partly reflects that most locations are far from the threshold; Section 7.10 shows the accuracy for the difficult cases near it.`),
  ...figure(IMG("phase7/02_confusion_matrices.png"), 6.5, "Confusion matrices: climatology rule, selected logistic regression, decision tree and gradient boosting."),
  ...figure(IMG("phase7/01_roc_curves.png"), 3.8, "ROC curves of all classifiers on the test months."),
  H2("7.8 Independent validation against ARGO floats"),
  P(`${n0(AR.n_matchups_cell_days)} ARGO profiles (${AR.n_floats} floats) on test days were quality-controlled, converted to potential temperature with TEOS-10, interpolated to the 15 depths and matched to the nearest grid cell on the same day. ARGO was never used for training, tuning or selection.`),
  table(["Compared with ARGO", "RMSE °C", "Bias °C", "r", "n"], ["clim", "pred", "glorys"].map((s) => [
    { clim: "Climatology", pred: "ML model (final)", glorys: "GLORYS (assimilates ARGO; upper bound)" }[s], f3(AR.overall[s].rmse), f3(AR.overall[s].bias), f3(AR.overall[s].r), n0(AR.overall[s].n)]), [3, 1, 1, 1, 1], { highlight: (r) => r[0].startsWith("ML") }),
  tcap("Validation against independent ARGO profiles."),
  P(`The model closes ${gapClosed}% of the gap between climatology and GLORYS against real in-situ data, and near the surface it is even slightly closer to ARGO than GLORYS. The caveat is that GLORYS assimilates ARGO, so ARGO is independent of our model and inputs but not of the training target.`),
  ...figure(IMG("phase6/04_argo_validation.png"), 6.4, "ARGO validation: RMSE and bias by depth, and scatter of predictions against ARGO."),
  H2("7.9 Oceanographic indicators and cyclones"),
  table(["Indicator", "Definition", "ML RMSE", "Climatology RMSE", "r"], [["D20", "Depth of the 20 °C isotherm (thermocline)"], ["D26", "Depth of the 26 °C isotherm"], ["TCHP", "ρ·cp·∫(T−26)dz above D26"], ["MLD", "First depth with T < T(10 m) − 0.5 °C"], ["OHC300", "Heat content 0–300 m"]].map(([k, d]) =>
    [k, d, `${f2(IND[k].model_vs_glorys.rmse)} ${IND[k].units}`, `${f2(IND[k].clim_vs_glorys.rmse)} ${IND[k].units}`, f3(IND[k].model_vs_glorys.r)]), [1, 2.8, 1.2, 1.4, 0.6]),
  tcap("Indicators computed from predicted profiles, compared with GLORYS."),
  ...figure(IMG("phase6/03_cyclone_tchp.png"), 6.4, "Tropical cyclone heat potential under cyclones Tauktae (14 May 2021) and Yaas (24 May 2021): truth, ML prediction, climatology."),
  H2("7.10 Realism checks: harder tests and confidence intervals"),
  P("The main test holds out whole months but still trains on the months on either side, so the model has seen the same year and largely the same ocean state. To estimate how the method would perform in a more realistic setting, the final model configuration was retrained and tested under three harder splits."),
  table(["Test setup", "RMSE °C", "Climatology RMSE °C", "Skill", "RMSE 100 m", "R² 100 m"], Object.entries({
    A_main_month_holdout: "Main test: whole months held out (Feb, May, Aug, Nov)",
    B1_temporal_train_JanJun_test_AugNov: "Unseen months ahead: train Jan–Jun, test Aug and Nov",
    B2_spatial_unseen_regions: `Unseen regions: ${AU.B_stricter_tests.held_out_blocks} of ${AU.B_stricter_tests.total_blocks} 5°×5° blocks held out`,
    B2_spatial_without_lat_lon: "Unseen regions, model without latitude/longitude",
    B3_temporal_and_spatial: "Unseen months and unseen regions (hardest)",
  }).map(([k, lab_]) => { const v = AU.B_stricter_tests.setups[k]; return [lab_, f3(v.rmse), f3(v.rmse_clim), f2(v.mean_skill), f2(v.rmse_100m), f2(v.r2_100m)]; }), [3.2, 0.8, 1.1, 0.7, 0.9, 0.8]),
  tcap("Final model configuration under progressively harder train/test splits (150,000 scored rows each)."),
  table(["Classifier (TCHP ≥ 60)", "Main test", "Unseen regions", "Unseen months and regions"], [["Logistic Regression (L1)", "logistic_l1"], ["Gradient Boosting", "gradient_boosting"], ["Climatology rule", "climatology_rule"]].map(([l, k]) =>
    [l, f3(AU.B_stricter_tests.classification.main[k].accuracy), f3(AU.B_stricter_tests.classification.B2_spatial[k].accuracy), f3(AU.B_stricter_tests.classification.B3_temporal_and_spatial[k].accuracy)]), [2.8, 1.4, 1.4, 1.4]),
  tcap("Classification accuracy under the same harder splits."),
  table(["Distance of true TCHP from the 60 kJ cm⁻² threshold", "Share of test rows", "Logistic L1 accuracy", "Climatology rule accuracy"],
    Object.entries(AU.D_classification_by_distance_to_threshold.bands).map(([k, v]) => [k, `${(100 * v.share_of_rows).toFixed(0)}%`, f3(v.model_accuracy), f3(v.climatology_rule_accuracy)]), [2.8, 1.3, 1.4, 1.5]),
  tcap("Classification accuracy by difficulty: the headline accuracy is dominated by easy cases."),
  P(`The regression errors grow as the test becomes harder: from ${f2(AU.B_stricter_tests.setups.A_main_month_holdout.rmse)} °C on the main test to ${f2(AU.B_stricter_tests.setups.B2_spatial_unseen_regions.rmse)} °C for unseen regions, ${f2(AU.B_stricter_tests.setups.B1_temporal_train_JanJun_test_AugNov.rmse)} °C for months ahead, and ${f2(AU.B_stricter_tests.setups.B3_temporal_and_spatial.rmse)} °C when both are unseen (skill ${f2(AU.B_stricter_tests.setups.B3_temporal_and_spatial.mean_skill)}). The model still beats the climatology in every case, but the main-test number is clearly optimistic. Removing latitude and longitude makes the unseen-region error slightly worse (${f2(AU.B_stricter_tests.setups.B2_spatial_without_lat_lon.rmse)} °C), so the model is not simply memorising locations. The classifier accuracy stays high under the harder splits because most locations are far from the threshold; within ±10 kJ cm⁻² of it, the accuracy is only ${(100 * AU.D_classification_by_distance_to_threshold.bands["within 10 of threshold"].model_accuracy).toFixed(0)}%.`),
  P(`Bootstrap confidence intervals (resampling the ${AU.C_bootstrap.method.match(/\d+/)[0]} test days with replacement, 1,000 times): test RMSE ${f3(AU.C_bootstrap.rmse.estimate)} °C [95% CI ${f3(AU.C_bootstrap.rmse.ci95[0])}–${f3(AU.C_bootstrap.rmse.ci95[1])}], pooled skill ${f2(AU.C_bootstrap.pooled_skill.estimate)} [${f2(AU.C_bootstrap.pooled_skill.ci95[0])}–${f2(AU.C_bootstrap.pooled_skill.ci95[1])}], classification accuracy ${f3(AU.C_bootstrap.classification_accuracy_logistic_l1.estimate)} [${f3(AU.C_bootstrap.classification_accuracy_logistic_l1.ci95[0])}–${f3(AU.C_bootstrap.classification_accuracy_logistic_l1.ci95[1])}]. These intervals only capture day-to-day sampling variation; the harder splits above are the better guide to real-world error.`),
  P(`Data integrity checks found no problems: no duplicate rows, train and test days at least ${AU.A_data_integrity.min_gap_days_train_test} days apart, processed temperatures identical to the raw GLORYS files (maximum difference ${f2(AU.A_data_integrity.spotcheck_target_vs_raw_glorys_max_abs_diff_C)} °C), processed SST within ${f3(AU.A_data_integrity.spotcheck_sst_vs_raw_ostia_mean_abs_diff_C)} °C of raw OSTIA, and no single feature correlating above 0.95 with the target (the strongest is ${AU.A_data_integrity.strongest_single_feature_vs_anomaly["0"].feature} at ${f2(AU.A_data_integrity.strongest_single_feature_vs_anomaly["0"].abs_r)}), which rules out an obvious leak.`),
  H2("7.11 Interpreting the metrics"),
  B("R² on absolute temperature (0.99) is inflated by the 30 °C to 6 °C range between the surface and 1000 m; even climatology scores 0.98. Skill versus climatology and RMSE are the honest measures."),
  B(`Climatology alone puts ${TOL.overall["1.0"].clim_pct.toFixed(0)}% of values within ±1 °C, so the contribution of the model is the improvement to ${TOL.overall["1.0"].model_pct.toFixed(0)}% and the ${redPct}% lower RMSE, and in the thermocline only ${TOL.per_depth_within_1C["100"].model_pct.toFixed(0)}% are within ±1 °C.`),
  B(`The results are not a product of leakage: whole months are held out, every choice was made on cross-validation, features use only past days, and the independent ARGO comparison confirms the improvement. The realistic error for new months and new regions is about ${f2(AU.B_stricter_tests.setups.B3_temporal_and_spatial.rmse)} °C (Section 7.10), higher than the main-test figure.`),
);

// ---------------- 8. Team matrix
body.push(H1("8. Team Responsibility/Self-contribution Matrix"),
  table(["Activity", "Tanmay Sangwan", "Tanmay Kandwal", "Aryan Bhutani", "Prashast"],
    ["Data Preprocessing & EDA", "Feature Engineering", "Model building", "Model comparisons", "Ensemble", "Hyperparameter tuning/Cross validation", "Classification and regularization", "ARGO validation and indicators", "Presentation/Interface UI", "Deployment", "Documentation"].map((a) => [a, "", "", "", ""]),
    [2.6, 1.1, 1.1, 1.1, 1.1]),
  tcap("Contribution of each team member."),
);

// ---------------- 9. Conclusions
body.push(H1("9. Conclusions"),
  P(`Carefully engineered machine learning reconstructs the subsurface temperature of the North Indian Ocean well from surface satellite data alone. The final gradient-boosting model achieves a test RMSE of ${f3(FT.overall.rmse)} °C (${redPct}% below climatology), ${TOL.overall["1.0"].model_pct.toFixed(0)}% of predictions within ±1 °C, and ${f3(AR.overall.pred.rmse)} °C against independent ARGO profiles. It removes the climatology's bias and roughly halves its errors for the thermocline depth (D20), cyclone heat potential (TCHP) and upper-ocean heat content. Under harder, more realistic tests (months ahead and ocean regions never seen in training) the error rises to about ${f2(AU.B_stricter_tests.setups.B3_temporal_and_spatial.rmse)} °C, still below the climatology's ${f2(AU.B_stricter_tests.setups.B3_temporal_and_spatial.rmse_clim)} °C; this is the figure we would expect in practice.`),
  B("Tree ensembles outperform single trees and linear models; sea level anomaly is the key thermocline signal, and SST controls only the top tens of metres."),
  B(`The classification task identifies cyclone-favourable ocean with ${(100 * CL.models.logistic_l1.accuracy).toFixed(1)}–${(100 * CL.models.gradient_boosting.accuracy).toFixed(1)}% accuracy and about 94% recall, against 66% recall for the climatology rule; near the threshold, where the decision is hard, accuracy falls to about ${(100 * AU.D_classification_by_distance_to_threshold.bands["within 10 of threshold"].model_accuracy).toFixed(0)}%.`),
  B("Regularization was demonstrated where it matters: an over-complex model overfits severely without it, while Ridge and Lasso restore generalisation and Lasso selects 17 of 861 features."),
  B("A leakage-free design (whole-month test split, cross-validation-only decisions, independent ARGO validation) makes the results defensible."),
  P([{ text: "Limitations: ", bold: true }, "only one year of data; GLORYS, used as truth, assimilates ARGO; predictions are smoother than reality; the model relies on location and is specific to this region."]),
  P([{ text: "Future work: ", bold: true }, "multi-year training, spatial-holdout tests, uncertainty estimates (for example quantile regression), clustering of ocean regimes (K-Means/DBSCAN) to train regime-specific models, and deployment as a web dashboard."]),
);

// ---------------- References
body.push(new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, children: [new TextRun("References")] }),
  ...[
    "Rebert, J.-P., Donguy, J.-R., Eldin, G., Wyrtki, K. (1985). Relations between sea level, thermocline depth, heat content, and dynamic height in the tropical Pacific Ocean. Journal of Geophysical Research, 90(C6), 11719–11725.",
    "Shay, L.K., Goni, G.J., Black, P.G. (2000). Effects of a warm oceanic feature on Hurricane Opal. Monthly Weather Review, 128(5), 1366–1383.",
    "Ali, M.M., Swain, D., Weller, R.A. (2004). Estimation of ocean subsurface thermal structure from surface parameters: a neural network approach. Geophysical Research Letters, 31, L20308.",
    "Buongiorno Nardelli, B., Santoleri, R. (2005). Methods for the reconstruction of vertical profiles from surface data: multivariate analyses, residual GEM, and variable temporal signals in the North Pacific Ocean. Journal of Atmospheric and Oceanic Technology, 22, 1762–1781.",
    "Guinehut, S., Dhomps, A.-L., Larnicol, G., Le Traon, P.-Y. (2012). High resolution 3-D temperature and salinity fields derived from in situ and satellite observations. Ocean Science, 8, 845–857.",
    "Nagamani, P.V., Ali, M.M., Goni, G.J. et al. (2012). Validation of satellite-derived tropical cyclone heat potential with in situ observations in the North Indian Ocean. Remote Sensing Letters, 3.",
    "Su, H., Wu, X., Yan, X.-H., Kidwell, A. (2015). Estimation of subsurface temperature anomaly in the Indian Ocean during recent global surface warming hiatus from satellite measurements: a support vector machine approach. Remote Sensing of Environment, 160, 63–71.",
    "Su, H., Li, W., Yan, X.-H. (2018). Retrieving temperature anomaly in the global subsurface and deeper ocean from satellite observations. Journal of Geophysical Research: Oceans, 123, 399–410.",
    "Su, H., Yang, X., Lu, W., Yan, X.-H. (2019). Estimating subsurface thermohaline structure of the global ocean using surface remote sensing observations. Remote Sensing, 11(13), 1598.",
    "Qi, J., Liu, C., Chi, J., Li, D., Gao, L., Yin, B. (2022). An ensemble-based machine learning model for estimation of subsurface thermal structure in the South China Sea. Remote Sensing, 14(13), 3207.",
    "Lellouche, J.-M. et al. (2021). The Copernicus global 1/12° oceanic and sea ice GLORYS12 reanalysis. Frontiers in Earth Science, 9, 698876.",
    "Good, S. et al. (2020). The current configuration of the OSTIA system for operational production of foundation sea surface temperature and ice concentration analyses. Remote Sensing, 12(4), 720.",
    "E.U. Copernicus Marine Service products: GLOBAL_MULTIYEAR_PHY_ENS_001_031, GLOBAL_MULTIYEAR_PHY_001_030, SST_GLO_SST_L4_REP_OBSERVATIONS_010_011, MULTIOBS_GLO_PHY_S_SURFACE_MYNRT_015_013, SEALEVEL_GLO_PHY_L4_MY_008_047, WIND_GLO_PHY_L4_MY_012_006.",
    "Argo (2000). Argo float data and metadata from the Global Data Assembly Centre (Argo GDAC). SEANOE. doi:10.17882/42182.",
    "Knapp, K.R. et al. (2010). The International Best Track Archive for Climate Stewardship (IBTrACS). Bulletin of the American Meteorological Society, 91, 363–376.",
    "Leipper, D.F., Volgenau, D. (1972). Hurricane heat potential of the Gulf of Mexico. Journal of Physical Oceanography, 2, 218–224.",
    "Large, W.G., Pond, S. (1981). Open ocean momentum flux measurements in moderate to strong winds. Journal of Physical Oceanography, 11, 324–336.",
    "McDougall, T.J., Barker, P.M. (2011). Getting started with TEOS-10 and the Gibbs Seawater (GSW) Oceanographic Toolbox. SCOR/IAPSO WG127.",
    "Pedregosa, F. et al. (2011). Scikit-learn: machine learning in Python. Journal of Machine Learning Research, 12, 2825–2830.",
    "Indian National Centre for Ocean Information Services (INCOIS), Ministry of Earth Sciences: problem statement on reconstructing subsurface ocean temperature from satellite observations.",
  ].map((t, i) => new Paragraph({ spacing: { after: 100, line: 276 }, indent: { left: 400, hanging: 400 }, children: [new TextRun({ text: `[${i + 1}] `, bold: true }), new TextRun(t)] })),
);

// ---------------- Appendix
body.push(new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, children: [new TextRun("Appendix")] }),
  H2("A. Code repository and reproduction"),
  P("All code, notebooks, results and documentation are public at github.com/Aryanbhutani14/Oceantemperatures. Raw data are not stored on GitHub; every phase is rebuilt by one command:"),
  ...["pip install -e \".[data,dev]\"", "python -m pytest -q", "python scripts/00_audit.py", "python scripts/01_download.py cmems --source all", "python scripts/02_harmonise.py --source all", "python scripts/03_build_cube.py ; python scripts/03_eda.py", "python scripts/04_features.py", "python scripts/05_models.py ; python scripts/05_ablation.py ; python scripts/05_final_model.py", "python scripts/06_evaluate.py", "python scripts/07_classification.py"].map((c) =>
    new Paragraph({ spacing: { after: 20 }, children: [new TextRun({ text: c, font: "Courier New", size: 18 })] })),
  H2("B. Linear regression by gradient descent (from scratch)"),
  ...fs.readFileSync(path.join(ROOT, "src", "oceanembed_ml", "models", "scratch.py"), "utf8").split(/\r?\n/).slice(13).map((l) =>
    new Paragraph({ spacing: { after: 0 }, children: [new TextRun({ text: l || " ", font: "Courier New", size: 16 })] })),
  H2("C. Notebooks"),
  B("01_data_audit: dataset catalogue, grid alignment, ARGO availability"),
  B("02_harmonisation: regridding operator and quality control"),
  B("03_eda: statistics, maps, correlations, PCA, outliers"),
  B("04_features: feature groups, relationships, PCA embedding"),
  B("05_models: cross-validation, test comparison, ablations, final model"),
  B("06_evaluation: full test grid, ARGO validation, indicators"),
  B("07_classification_regularization: classifiers, ROC, confusion matrices, validation curves"),
);

// captions go ABOVE their tables (kept with the table, never orphaned)
for (let i = 0; i < body.length - 1; i++) {
  if (body[i] instanceof Table && body[i + 1] && body[i + 1]._isCaption) { const c = body[i + 1]; body[i + 1] = body[i]; body[i] = c; i++; }
}

const doc = new Document({
  creator: "OceanEmbed-ML team", title: "OceanEmbed-ML Project Report",
  styles: {
    default: { document: { run: { font: "Calibri", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: "Cambria", size: 32, bold: true, color: NAVY }, paragraph: { spacing: { before: 240, after: 200 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: "Cambria", size: 25, bold: true, color: H2C }, paragraph: { spacing: { before: 240, after: 100 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [
    { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    { reference: "steps", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] },
  ] },
  features: { updateFields: true },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], size: 18, color: "5E6B78" })] })] }) },
    children: body,
  }],
});

Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("wrote", OUT); });
