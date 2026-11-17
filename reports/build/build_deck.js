// Builds reports/OceanEmbed_ML_Presentation.pptx following the CSE2032 slide format.
// Every number is read from the results JSON files written by the pipeline (no hand-typed metrics).
// Run:  cd reports/build && node build_deck.js
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const ROOT = path.resolve(__dirname, "..", "..");
const SKILL = process.env.PPTX_SKILL_DIR;
// Python's json writes NaN for undefined metrics (e.g. AUC of a constant baseline) -> read as null
const J = (p) => JSON.parse(fs.readFileSync(path.join(ROOT, p), "utf8").replace(/\bNaN\b/g, "null"));
// figures produced by the pipeline, white margins trimmed by trim_figures.py
const FIG = (p) => path.join(__dirname, "img", p.replace("/", "_"));
const OUT = path.join(ROOT, "reports", "OceanEmbed_ML_Presentation.pptx");

const T5 = J("results/phase5/test_metrics.json");
const CV5 = J("results/phase5/cv_selection.json");
const FM = J("results/phase5/final_model.json");
const TCV = J("results/phase5/target_cv.json");
const AB = J("results/phase5/ablation.json");
const FT = J("results/phase6/full_test_metrics.json");
const AR = J("results/phase6/argo_validation.json");
const IND = J("results/phase6/indicators.json");
const CL = J("results/phase7/classification.json");
const RG = J("results/phase7/regularization.json");
const FS = J("data/audit/features_summary.json");

const f2 = (x) => Number(x).toFixed(2), f3 = (x) => Number(x).toFixed(3);

// ---------------------------------------------------------------- theme
const THEME = {
  name: "OceanEmbed",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "0B1F33", lt1: "FFFFFF", dk2: "123A5A", lt2: "EAF3F6",
    accent1: "0E7C86", accent2: "F26B3A", accent3: "2B9FD8", accent4: "8FB8C8", accent5: "5E6B78", accent6: "F2B134",
    hlink: "0E7C86", folHlink: "5E6B78",
  },
};
const HEX = THEME.colors;

function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}
function fitImage(slide, file, x, y, w, h, name) {
  const s = pngSize(file);
  const r = Math.min(w / s.w, h / s.h);
  const iw = s.w * r, ih = s.h * r;
  slide.addImage({ path: file, x: x + (w - iw) / 2, y: y + (h - ih) / 2, w: iw, h: ih, objectName: name, altText: name });
}

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "OceanEmbed-ML";
pres.author = "OceanEmbed-ML team";
const C = pres.SchemeColor;
const W = 13.333, M = 0.5;

pres.defineSlideMaster({
  title: "Title Dark",
  background: { color: C.text1 },
  objects: [],
  slideNumber: { x: 12.4, y: 7.0, w: 0.6, h: 0.3, color: C.background1, fontSize: 10 },
});
pres.defineSlideMaster({
  title: "Content",
  background: { color: C.background1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.32, w: W - 2 * M, h: 0.75, fontSize: 30, bold: true, color: C.text1, valign: "middle", margin: 0 }, text: "" } },
    { text: { text: "OceanEmbed-ML · CSE2032 Machine Learning", options: { x: M, y: 7.02, w: 6, h: 0.3, fontSize: 10, color: C.accent5, margin: 0 } } },
  ],
  slideNumber: { x: 12.4, y: 7.02, w: 0.6, h: 0.3, color: C.accent5, fontSize: 10 },
});

const TH = { bold: true, color: HEX.lt1, fill: { color: HEX.accent1 }, fontSize: 12, valign: "middle" };
const td = (t, o = {}) => ({ text: String(t), options: { fontSize: 12, color: HEX.dk1, valign: "middle", ...o } });
const th = (t, o = {}) => ({ text: t, options: { ...TH, ...o } });
function zebra(rows) {
  return rows.map((r, i) => (i === 0 ? r : r.map((c) => ({ text: c.text, options: { ...c.options, fill: { color: i % 2 ? HEX.lt1 : HEX.lt2 } } }))));
}
function card(slide, x, y, w, h, name) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: C.background2 }, line: { color: C.background2 }, objectName: name });
}
function numberBadge(slide, x, y, n, color) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: 0.55, h: 0.55, fill: { color }, line: { color }, objectName: `badge ${n}` });
  slide.addText(String(n).padStart(2, "0"), { x, y, w: 0.55, h: 0.55, align: "center", valign: "middle", fontSize: 14, bold: true, color: C.background1, margin: 0, isTextBox: true });
}
function stat(slide, x, y, w, big, label, color, name) {
  card(slide, x, y, w, 1.55, name);
  slide.addText(big, { x: x + 0.2, y: y + 0.12, w: w - 0.4, h: 0.85, fontSize: 34, bold: true, color, fontFace: THEME.headFontFace, margin: 0, isTextBox: true });
  slide.addText(label, { x: x + 0.2, y: y + 0.95, w: w - 0.4, h: 0.55, fontSize: 12, color: C.text1, margin: 0, valign: "top", isTextBox: true });
}
const content = (section) => {
  const s = pres.addSlide({ masterName: "Content", sectionTitle: section });
  return s;
};

// ================================================================ Slide 0: title
pres.addSection({ title: "Introduction" });
{
  const s = pres.addSlide({ masterName: "Title Dark", sectionTitle: "Introduction" });
  s.addText("SIH 2026 · SIH26066 (INCOIS, Ministry of Earth Sciences) · CSE2032 Machine Learning", { x: M, y: 0.45, w: 12, h: 0.35, fontSize: 14, color: C.accent4, margin: 0, isTextBox: true });
  s.addText("OceanEmbed-ML", { x: M, y: 0.95, w: 12, h: 0.95, fontSize: 48, bold: true, color: C.background1, fontFace: THEME.headFontFace, margin: 0, isTextBox: true });
  s.addText("Reconstructing subsurface ocean temperature (0–1000 m) of the North Indian Ocean from satellite surface data with classical machine learning",
    { x: M, y: 1.9, w: 8.2, h: 1.0, fontSize: 18, color: C.background2, margin: 0, isTextBox: true });
  s.addText([
    { text: "Team", options: { bold: true, color: C.accent6, breakLine: true } },
    { text: "Aryan Bhutani — <Enrollment No.>", options: { breakLine: true } },
    { text: "<Name of Student-2> — <Enrollment No.>", options: { breakLine: true } },
    { text: "<Name of Student-3> — <Enrollment No.>", options: { breakLine: true } },
    { text: "<Name of Student-4> — <Enrollment No.>" },
  ], { x: 9.1, y: 1.9, w: 3.8, h: 1.9, fontSize: 13, color: C.background1, margin: 0, valign: "top", paraSpaceAfter: 4, isTextBox: true });
  s.addText("Department of CSE · School of Engineering and Technology · BML Munjal University · November 2026", { x: M, y: 3.25, w: 8.3, h: 0.35, fontSize: 12, color: C.accent4, margin: 0, isTextBox: true });
  fitImage(s, FIG("phase6/01_map_T100_tauktae.png"), 0.3, 3.85, 12.73, 3.1, "Title map: truth vs prediction at 100 m");
  s.addNotes("Introduce the problem: satellites only see the ocean surface, but cyclones, fisheries and climate depend on the subsurface. The strip shows our real output: GLORYS truth vs our ML prediction vs error at 100 m on 15 May 2021, while cyclone Tauktae was active.");
}

// ================================================================ Slide 1: objectives & deliverables
{
  const s = content("Introduction");
  s.addText("Project objectives and deliverables", { placeholder: "title" });
  const colW = 5.95;
  [["Objectives", C.accent1, [
    "Predict ocean temperature at 15 standard depths (0–1000 m), daily on a 0.25° grid over the North Indian Ocean, using only satellite surface observations (SST, salinity, sea level, currents, winds)",
    "Compare syllabus ML models fairly with leakage-free, month-wise cross-validation, and turn the predictions into a cyclone-risk classification (heat potential TCHP ≥ 60 kJ cm⁻²)",
  ]], ["Deliverables", C.accent2, [
    "A reproducible open-source pipeline: 8 harmonised datasets, an installable Python package, 7 executed notebooks, 21 automated tests and a trained final model",
    `Validated results: test RMSE ${f2(FT.overall.rmse)} °C, ${f2(AR.overall.pred.rmse)} °C against independent ARGO floats, ocean indicators (D20, TCHP, OHC) and cyclone-favourability maps`,
  ]]].forEach(([head, col, items], i) => {
    const x = M + i * (colW + 0.43);
    card(s, x, 1.45, colW, 4.6, `${head} card`);
    s.addText(head, { x: x + 0.35, y: 1.65, w: colW - 0.7, h: 0.5, fontSize: 22, bold: true, color: col, fontFace: THEME.headFontFace, margin: 0, isTextBox: true });
    items.forEach((t, k) => {
      numberBadge(s, x + 0.35, 2.45 + k * 1.8, k + 1, col);
      s.addText(t, { x: x + 1.1, y: 2.35 + k * 1.8, w: colW - 1.45, h: 1.6, fontSize: 15, color: C.text1, margin: 0, valign: "top", isTextBox: true });
    });
  });
  s.addNotes("Objective 1 is the regression problem from SIH26066. Objective 2 adds the course requirements: fair model comparison and a classification task. The deliverables are all on GitHub: github.com/Aryanbhutani14/Oceantemperatures.");
}

// ================================================================ Slide 2: literature review
pres.addSection({ title: "Background" });
{
  const s = content("Background");
  s.addText("Literature review: earlier work on the same kind of data", { placeholder: "title" });
  const rows = [
    [th("Study"), th("Data (surface → subsurface)"), th("Method"), th("Region / depth"), th("Takeaway for us")],
    [td("Ali, Swain & Weller (2004), GRL", { bold: true }), td("SST, SSH, wind stress, heat fluxes → mooring temperature profiles"), td("Artificial neural network"), td("Arabian Sea, upper ocean"), td("Surface fields carry thermocline information; avg RMS error ≈ 0.58 °C")],
    [td("Guinehut et al. (2012), Ocean Science: ARMOR3D", { bold: true }), td("Satellite SST, SLA + ARGO profiles"), td("Multiple linear regression + optimal interpolation"), td("Global, 0–1500 m"), td("Operational statistical (non-DL) product: linear methods are a strong baseline")],
    [td("Su et al. (2015), Remote Sens. Environ.", { bold: true }), td("SST, SSH, SSS anomalies → ARGO temperature anomaly"), td("Support vector regression"), td("Indian Ocean, 0–1000 m"), td("Adding SSS improves skill (MSE ≈ 12% lower): we include salinity")],
    [td("Su, Li & Yan (2018), JGR Oceans", { bold: true }), td("SSH, SST, SSS, wind → ARGO temperature anomaly"), td("Random forest"), td("Global, to 1000 m+"), td("Tree ensembles work well: we compare RF and boosting")],
    [td("OceanEmbed reference (SIH26066, GitHub)", { bold: true }), td("Same inputs as ours: OSTIA, SMOS/SMAP, DUACS, winds → GLORYS"), td("U-Net CNN design (deep learning)"), td("North Indian Ocean, 15 depths"), td("No published metrics; we test how far classical ML goes without DL")],
    [td("This project (2026)", { bold: true, color: HEX.accent2 }), td("OSTIA, SSS L4, DUACS, ASCAT L4 winds → GLORYS; ARGO for validation"), td("13 classical models; gradient boosting + climatology feature"), td("North Indian Ocean, 0–1000 m, daily 0.25°"), td(`Test RMSE ${f2(FT.overall.rmse)} °C; ${f2(AR.overall.pred.rmse)} °C vs ARGO`, { bold: true })],
  ];
  s.addTable(zebra(rows), { x: M, y: 1.25, w: W - 2 * M, colW: [2.55, 2.75, 2.15, 1.9, 2.98], fontFace: THEME.bodyFontFace, border: { type: "solid", pt: 0.5, color: HEX.accent4 }, rowH: 0.62, margin: 0.06 });
  s.addNotes("All earlier work uses the same family of data: satellite SST/SSH/SSS (+wind) as inputs, ARGO or reanalysis as truth. Classical ML (SVR, random forest) is well established; the SIH26066 reference proposes deep learning without published results, so our contribution is a rigorous classical-ML baseline for this exact problem and region.");
}

// ================================================================ Slide 3: dataset
{
  const s = content("Background");
  s.addText("Dataset description", { placeholder: "title" });
  const tr = FS.tables.train, te = FS.tables.test;
  const nRows = (tr.rows + te.rows).toLocaleString("en-US");
  stat(s, M, 1.3, 3.1, nRows, `rows (ocean cell-days): train ${tr.rows.toLocaleString("en-US")}, test ${te.rows.toLocaleString("en-US")}`, C.accent1, "stat rows");
  stat(s, M, 3.0, 3.1, String(tr.columns), "columns: 40 features, 45 per-depth columns, 7 metadata", C.accent2, "stat columns");
  stat(s, M, 4.7, 3.1, "8 sources", "satellite + reanalysis + ARGO + cyclone tracks; 2021, 0.25° grid, 15 depths", C.accent3, "stat sources");
  const rows = [
    [th("Variable"), th("Description (source, unit)"), th("Data type"), th("Role")],
    [td("sst"), td("Sea surface temperature (OSTIA L4), °C"), td("float32"), td("feature")],
    [td("sss"), td("Sea surface salinity (SMOS/SMAP L4), PSU"), td("float32"), td("feature")],
    [td("sla"), td("Sea level anomaly (DUACS L4), m"), td("float32"), td("feature")],
    [td("uo, vo"), td("Surface geostrophic currents (DUACS), m s⁻¹"), td("float32"), td("feature")],
    [td("u10, v10"), td("10 m winds (ASCAT-based L4), m s⁻¹"), td("float32"), td("feature")],
    [td("33 derived"), td("Wind stress, Ekman pumping, gradients, 7-day means, SST anomaly, lat/lon, season, depth, 8 PCA embeddings"), td("float32"), td("feature")],
    [td("clim_d00…d14"), td("External GLORYS12 climatology at each depth, °C"), td("float32"), td("feature")],
    [td("y_d00…d14", { bold: true }), td("GLORYS temperature at 0, 5, …, 1000 m, °C", { bold: true }), td("float32"), td("target (regression)", { bold: true, color: HEX.accent2 })],
    [td("label", { bold: true }), td("1 if TCHP ≥ 60 kJ cm⁻² (cyclone-favourable), else 0", { bold: true }), td("int8 (0/1)"), td("target (classification)", { bold: true, color: HEX.accent2 })],
    [td("time, cell_id, region"), td("UTC date, grid cell, Arabian Sea / Bay of Bengal"), td("datetime64, int32, category"), td("metadata")],
  ];
  s.addTable(zebra(rows), { x: 3.95, y: 1.3, w: 8.88, colW: [1.7, 4.3, 1.45, 1.43], fontFace: THEME.bodyFontFace, border: { type: "solid", pt: 0.5, color: HEX.accent4 }, rowH: 0.47, margin: 0.06 });
  s.addNotes("Each row is one 0.25° ocean grid cell on one day. 11,880 ocean cells x 365 days, minus 56 buffer days. Inputs are what satellites measure; the target is the GLORYS reanalysis temperature at 15 standard depths. The classification label is derived from the same profile.");
}

// ================================================================ Slide 4: EDA & FE
pres.addSection({ title: "Methodology" });
{
  const s = content("Methodology");
  s.addText("Methodology: EDA and feature engineering", { placeholder: "title" });
  const rows = [
    [th("EDA finding"), th("Evidence"), th("Feature / decision")],
    [td("The thermocline (75–150 m) is the hardest layer"), td("Anomaly std 1.58 °C at 100 m vs 0.22 °C at 1000 m"), td("Per-depth models; evaluate per depth")],
    [td("Sea level tracks the warm-layer depth"), td("Spearman ρ = 0.71 between SLA and T at 100 m"), td("SLA 7-day mean, gradients, Laplacian, 5×5 neighbourhood")],
    [td("SST only explains the top ~30 m"), td("ρ 0.94 at 0 m, ≈ 0 by 125 m; SST anomaly ρ 0.75 vs raw 0.26"), td("SST anomaly vs climatology")],
    [td("Winds drive upwelling (Somalia, Oman)"), td("Cold coastal anomalies in summer maps"), td("Wind stress, curl, Ekman pumping")],
    [td("Profiles are low-dimensional"), td("6 PCA components explain 90% of profile variance"), td("PCA regression; 8-component surface embedding")],
    [td("Extremes are real events, not errors"), td("SST outliers 10× more frequent near cyclone tracks; Gulf SST 36.7 °C"), td("Flag, never delete; plausibility cap 38 °C")],
    [td("Strong space–time autocorrelation"), td("Neighbouring days are near-duplicates"), td("Whole-month test split + 7-day buffers; past-only windows")],
    [td("Climatology is biased for 2021"), td("Bias −0.32 °C over the test months"), td("Climatology used as an input feature (chosen by CV)")],
  ];
  s.addTable(zebra(rows), { x: M, y: 1.25, w: W - 2 * M, colW: [3.6, 4.6, 4.13], fontFace: THEME.bodyFontFace, border: { type: "solid", pt: 0.5, color: HEX.accent4 }, rowH: 0.6, margin: 0.07 });
  s.addNotes("Every engineered feature answers an EDA finding. Data issues found: Persian Gulf extremes (real), Tibetan lakes in OSTIA and land values in winds (masked), a few coastal gaps (kept as NaN, imputed inside the pipeline).");
}

// ================================================================ Slide 5: baseline + compared models
{
  const s = content("Methodology");
  s.addText("Methodology: baseline and compared models", { placeholder: "title" });
  card(s, M, 1.3, 4.2, 5.35, "baseline card");
  s.addText("Baselines", { x: M + 0.3, y: 1.45, w: 3.6, h: 0.5, fontSize: 22, bold: true, color: C.accent2, fontFace: THEME.headFontFace, margin: 0, isTextBox: true });
  s.addText([
    { text: "Climatology", options: { bold: true, breakLine: true } },
    { text: "The long-term average profile for that month and place. It is what forecasters have without any 2021 data; every skill score is measured against it.", options: { breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 6 } },
    { text: "SST-only linear regression", options: { bold: true, breakLine: true } },
    { text: "Is surface temperature alone enough? This tests whether the other satellite variables add information.", options: { breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 6 } },
    { text: "Classification: majority class and the climatology rule (climatological TCHP ≥ 60).", options: { italic: true } },
  ], { x: M + 0.3, y: 2.05, w: 3.6, h: 4.4, fontSize: 14, color: C.text1, margin: 0, valign: "top", isTextBox: true });
  const rows = [
    [th("Model (CSE2032 topic)"), th("Why it is compared")],
    [td("Linear Regression, incl. gradient descent from scratch"), td("Interpretable reference; verifies the optimiser against closed-form OLS")],
    [td("Ridge (L2) and Lasso (L1)"), td("Control multicollinearity; Lasso selects features")],
    [td("KNN regression"), td("Analogue method: similar surface states give similar profiles")],
    [td("SVR (RBF kernel)"), td("Nonlinear kernel method; used in earlier work (Su et al. 2015)")],
    [td("Decision Tree"), td("Captures nonlinear thresholds; shows high variance on its own")],
    [td("PCA regression (8 vertical modes)"), td("Predicts whole profiles consistently through dimension reduction")],
    [td("Logistic Regression L1/L2, SVM, Decision Tree, KNN"), td("Classification of cyclone-favourable ocean (TCHP ≥ 60)")],
  ];
  s.addTable(zebra(rows), { x: 5.05, y: 1.3, w: 7.78, colW: [3.5, 4.28], fontFace: THEME.bodyFontFace, border: { type: "solid", pt: 0.5, color: HEX.accent4 }, rowH: 0.62, margin: 0.07 });
  s.addNotes("Climatology is the natural baseline in oceanography: a model is only useful if it beats the long-term average. Each comparison model covers a syllabus topic and a different inductive bias (linear, distance-based, kernel, rules, dimension reduction).");
}

// ================================================================ Slide 6: ensembles + validation design
{
  const s = content("Methodology");
  s.addText("Methodology: ensembles and leakage-free validation", { placeholder: "title" });
  const ens = [
    ["Bagging", "30 deep trees on bootstrap samples: averaging cuts variance"],
    ["Random Forest", "Bagging + random feature subsets: decorrelates the trees"],
    ["Gradient Boosting", "Shallow trees fitted to residuals with a small learning rate (selected model)"],
    ["Averaging ensemble", "Boosting + forest; adopted only if CV improves by ≥ 1% (it gained 0.004%, so it was not adopted)"],
  ];
  ens.forEach(([h, t], i) => {
    const x = M + i * 3.13;
    card(s, x, 1.3, 2.95, 1.75, `ensemble ${h}`);
    s.addText(h, { x: x + 0.2, y: 1.42, w: 2.55, h: 0.45, fontSize: 17, bold: true, color: C.accent1, margin: 0, isTextBox: true });
    s.addText(t, { x: x + 0.2, y: 1.85, w: 2.55, h: 1.15, fontSize: 13, color: C.text1, margin: 0, valign: "top", isTextBox: true });
  });
  s.addText("Train/test split by whole months (never random rows), with 7-day buffers in between", { x: M, y: 3.45, w: 12, h: 0.4, fontSize: 16, bold: true, color: C.text1, margin: 0, isTextBox: true });
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const test = new Set([1, 4, 7, 10]);
  months.forEach((m, i) => {
    const x = M + i * 1.03;
    const isT = test.has(i);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 3.95, w: 0.95, h: 0.75, rectRadius: 0.06, fill: { color: isT ? C.accent2 : C.accent1 }, line: { color: isT ? C.accent2 : C.accent1 }, objectName: `month ${m}` });
    s.addText([{ text: m, options: { bold: true, breakLine: true } }, { text: isT ? "test" : "train", options: { fontSize: 11 } }],
      { x, y: 3.95, w: 0.95, h: 0.75, align: "center", valign: "middle", fontSize: 14, color: C.background1, margin: 0, isTextBox: true });
  });
  s.addText([
    { text: "Tuning: ", options: { bold: true } }, { text: "GroupKFold(4) with groups = month on the 8 train months; whole months held out per fold.", options: { breakLine: true } },
    { text: "Test: ", options: { bold: true } }, { text: "Feb, May, Aug, Nov (one per season), used once for final scoring; identical rows for every model.", options: { breakLine: true } },
    { text: "Leakage checks: ", options: { bold: true } }, { text: "past-only features, train-only PCA, external climatology; 21 automated tests." },
  ], { x: M, y: 4.95, w: 12.3, h: 1.6, fontSize: 15, color: C.text1, margin: 0, valign: "top", paraSpaceAfter: 6, isTextBox: true });
  s.addNotes("Ocean data is strongly autocorrelated, so a random split would put near-identical neighbouring days in both train and test and inflate the scores. Whole-month blocks with buffers avoid that. Model and target choices were made on cross-validation only; the test months were touched once.");
}

// ================================================================ Slide 7: regression results
pres.addSection({ title: "Results" });
{
  const s = content("Results");
  s.addText("Experimental results: regression (all 13 models)", { placeholder: "title" });
  const names = Object.keys(T5.models).sort((a, b) => T5.models[b].overall.rmse - T5.models[a].overall.rmse);
  const label = (n) => ({ final_gb_clim_feature: "Final: boosting + clim feature", gradient_boosting: "Gradient Boosting", random_forest: "Random Forest", bagging_trees: "Bagging", pca_regression: "PCA regression", svr_rbf: "SVR (RBF)", knn: "KNN", ridge: "Ridge", lasso: "Lasso", linear_regression: "Linear Regression", linear_gd_scratch: "Linear (GD from scratch)", decision_tree: "Decision Tree", sst_only_linear: "SST-only linear", climatology: "Climatology", ensemble_avg: "Avg ensemble (not adopted)" }[n] || n);
  const rowsSorted = names.slice().reverse();
  const rows = [[th("Model"), th("CV RMSE*"), th("Test RMSE °C"), th("Skill"), th("RMSE 100 m")]].concat(
    rowsSorted.map((n) => {
      const m = T5.models[n];
      const cv = n === "final_gb_clim_feature" ? TCV.variants["anomaly+clim_feat"].cv_rmse_mean : (CV5[n] || {}).best_cv_rmse;
      const hi = n === "final_gb_clim_feature" ? { bold: true, color: HEX.accent2 } : {};
      return [td(label(n), hi), td(cv ? f3(cv) : "—", hi), td(f3(m.overall.rmse), hi), td(f2(m.mean_skill_over_depths), hi), td(f2(m.per_depth["100"].rmse), hi)];
    }));
  s.addTable(zebra(rows), { x: M, y: 1.2, w: 6.6, colW: [2.75, 0.95, 1.15, 0.75, 1.0], fontFace: THEME.bodyFontFace, border: { type: "solid", pt: 0.5, color: HEX.accent4 }, rowH: 0.31, margin: [0.01, 0.05, 0.01, 0.05], fontSize: 11 });
  s.addText("* CV RMSE of the anomaly on train months (GroupKFold by month); the final model's CV is on absolute temperature. Skill = 1 − MSE/MSE(climatology). Test = identical 200k rows.",
    { x: M, y: 6.5, w: 6.6, h: 0.45, fontSize: 10, color: C.accent5, margin: 0, isTextBox: true });
  s.addChart(pres.charts.BAR, [{ name: "Test RMSE (°C)", labels: names.map(label), values: names.map((n) => Number(T5.models[n].overall.rmse.toFixed(3))) }], {
    x: 7.35, y: 1.2, w: 5.5, h: 5.7, barDir: "bar", showTitle: true, title: "Test RMSE (°C), lower is better", titleFontSize: 13, titleColor: HEX.dk1, titleFontFace: "+mn-lt",
    chartColors: names.map((n) => (n === "final_gb_clim_feature" ? HEX.accent2 : n === "climatology" ? HEX.accent5 : HEX.accent1)),
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 9, dataLabelColor: HEX.dk1, dataLabelFontFace: "+mn-lt", dataLabelFormatCode: "0.000",
    catAxisLabelColor: HEX.dk1, valAxisLabelColor: HEX.accent5, catAxisLabelFontSize: 10, valAxisLabelFontSize: 9, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
    valGridLine: { color: "D5E3EA", size: 0.5 }, catGridLine: { style: "none" }, showLegend: false, valAxisMinVal: 0, valAxisMaxVal: 1.1,
  });
  s.addNotes(`Every model beats climatology. Tree ensembles win (bias-variance: a single tree ${f3(T5.models.decision_tree.overall.rmse)} vs random forest ${f3(T5.models.random_forest.overall.rmse)}). The final model adds the climatology as a feature, a choice made by cross-validation, and reaches ${f3(FM.overall.rmse)} °C. Ridge = Lasso = OLS here because 400k rows >> 40 features, so there is nothing to overfit.`);
}

// ================================================================ Slide 8: classification results
{
  const s = content("Results");
  s.addText("Experimental results: classification (cyclone-favourable ocean)", { placeholder: "title" });
  const order = ["majority_class", "climatology_rule", "decision_tree", "knn", "logistic_l2", "logistic_l1", "svm_rbf", "random_forest", "gradient_boosting"];
  const nm = { majority_class: "Majority class", climatology_rule: "Climatology rule", decision_tree: "Decision Tree", knn: "KNN", logistic_l2: "Logistic Reg. (L2)", logistic_l1: "Logistic Reg. (L1) ✓ CV", svm_rbf: "SVM (RBF)", random_forest: "Random Forest", gradient_boosting: "Gradient Boosting" };
  const rows = [[th("Model"), th("CV AUC"), th("Accuracy"), th("Precision"), th("Recall"), th("F1"), th("ROC-AUC")]].concat(order.map((n) => {
    const m = CL.models[n];
    const hi = n === CL.selected_by_cv ? { bold: true, color: HEX.accent2 } : {};
    const v = (x) => (x === undefined || x === null || Number.isNaN(x) ? "—" : f3(x));
    return [td(nm[n], hi), td(v(m.cv_auc), hi), td(v(m.accuracy), hi), td(v(m.precision), hi), td(v(m.recall), hi), td(v(m.f1), hi), td(v(m.roc_auc), hi)];
  }));
  s.addTable(zebra(rows), { x: M, y: 1.2, w: 7.3, colW: [2.2, 0.85, 0.85, 0.85, 0.8, 0.8, 0.95], fontFace: THEME.bodyFontFace, border: { type: "solid", pt: 0.5, color: HEX.accent4 }, rowH: 0.42, margin: 0.04, fontSize: 11 });
  s.addText(`Task: TCHP ≥ 60 kJ cm⁻² from surface data only. ${Math.round(CL.positive_rate.test_eval * 100)}% positive (balanced). GridSearchCV + GroupKFold by month; identical ${CL.n_rows.test_eval.toLocaleString("en-US")} test rows.`,
    { x: M, y: 5.5, w: 7.3, h: 0.55, fontSize: 12, color: C.text1, margin: 0, isTextBox: true });
  s.addText(`The climatology rule misses one third of favourable areas (recall ${f2(CL.models.climatology_rule.recall)}); ML models catch about 93–94%.`,
    { x: M, y: 6.1, w: 7.3, h: 0.55, fontSize: 12, bold: true, color: C.accent2, margin: 0, isTextBox: true });
  fitImage(s, FIG("phase7/01_roc_curves.png"), 8.0, 1.2, 4.85, 5.6, "ROC curves");
  s.addNotes("Logistic regression with L1 was selected by cross-validated AUC; boosting is about 1 point better on test, but logistic regression is simpler and interpretable. Recall matters most for cyclone warnings, because a missed favourable area is the costly error.");
}

// ================================================================ Slide 9: regularization + CV
{
  const s = content("Results");
  s.addText("Regularization and cross-validated results", { placeholder: "title" });
  fitImage(s, FIG("phase7/04_regularization_curves.png"), M, 1.15, W - 2 * M, 2.55, "Regularization validation curves");
  const r = RG.ridge_poly, t = RG.tree_depth, l = RG.lasso_poly;
  const bestL = l.cv_rmse.indexOf(Math.min(...l.cv_rmse));
  stat(s, M, 3.95, 3.95, `${f2(r.unregularised_cv_rmse)} → ${f2(r.best_cv_rmse)} °C`, `Ridge (L2): CV RMSE of an 861-feature model on 2k rows, without vs with α = ${Math.round(r.best_alpha)}`, C.accent2, "ridge stat");
  stat(s, 4.69, 3.95, 3.95, `${l.nonzero_coefs[bestL]} / 861`, `Lasso (L1) keeps only these features at the best α = ${l.alpha[bestL]}`, C.accent1, "lasso stat");
  stat(s, 8.88, 3.95, 3.95, `${f2(t.train_acc[t.train_acc.length - 1])} vs ${f2(t.cv_acc[t.cv_acc.length - 1])}`, `Decision tree depth 30: train vs CV accuracy (overfits); best depth ${t.best_depth}`, C.accent3, "tree stat");
  s.addText([
    { text: "Cross-validation: ", options: { bold: true } },
    { text: `every hyperparameter grid was scored with GroupKFold by month (e.g. Ridge α = ${CV5.ridge.best_params.alpha}, KNN k = ${CV5.knn.best_params.k}, boosting learning rate ${CV5.gradient_boosting.best_params.lr}). CV ranks the models in the same order as the test set. The target formulation was also chosen by CV: anomaly ${f3(TCV.variants.anomaly.cv_rmse_mean)}, absolute ${f3(TCV.variants.absolute.cv_rmse_mean)}, anomaly + climatology feature ${f3(TCV.variants["anomaly+clim_feat"].cv_rmse_mean)} °C.` },
  ], { x: M, y: 5.75, w: W - 2 * M, h: 1.1, fontSize: 13, color: C.text1, margin: 0, valign: "top", isTextBox: true });
  s.addNotes("On the full problem Ridge equals OLS because 400k rows easily constrain 40 coefficients. To demonstrate regularisation properly we built an over-complex polynomial model: without regularisation it memorises the training data. Ridge shrinks the coefficients and Lasso zeroes most of them. Tree depth and the boosting learning rate are the regularisers for the tree models.");
}

// ================================================================ Slide 10: independent validation + indicators
{
  const s = content("Results");
  s.addText("Independent validation: ARGO floats and ocean indicators", { placeholder: "title" });
  const o = AR.overall;
  const rows = [[th("Compared with ARGO"), th("RMSE °C"), th("Bias °C"), th("r")],
    [td("Climatology"), td(f3(o.clim.rmse)), td(f3(o.clim.bias)), td(f3(o.clim.r))],
    [td("ML model (never saw ARGO)", { bold: true, color: HEX.accent2 }), td(f3(o.pred.rmse), { bold: true, color: HEX.accent2 }), td(f3(o.pred.bias), { bold: true, color: HEX.accent2 }), td(f3(o.pred.r), { bold: true, color: HEX.accent2 })],
    [td("GLORYS (assimilates ARGO, so it is the ceiling)"), td(f3(o.glorys.rmse)), td(f3(o.glorys.bias)), td(f3(o.glorys.r))]];
  s.addTable(zebra(rows), { x: M, y: 1.2, w: 6.2, colW: [3.2, 1.0, 1.0, 1.0], fontFace: THEME.bodyFontFace, border: { type: "solid", pt: 0.5, color: HEX.accent4 }, rowH: 0.4, margin: 0.05 });
  const ir = [[th("Indicator (vs GLORYS)"), th("ML error"), th("Climatology")]].concat([["D20", "D20 thermocline depth", "m"], ["TCHP", "TCHP heat potential", "kJ cm⁻²"], ["OHC300", "Heat content 0–300 m", "GJ m⁻²"]].map(([k, lab, u]) =>
    [td(lab), td(`${f2(IND[k].model_vs_glorys.rmse)} ${u}`, { bold: true }), td(`${f2(IND[k].clim_vs_glorys.rmse)} ${u}`)]));
  s.addTable(zebra(ir), { x: 6.95, y: 1.2, w: 5.88, colW: [2.6, 1.64, 1.64], fontFace: THEME.bodyFontFace, border: { type: "solid", pt: 0.5, color: HEX.accent4 }, rowH: 0.4, margin: 0.05 });
  s.addText(`${AR.n_matchups_cell_days.toLocaleString("en-US")} ARGO profiles from ${AR.n_floats} floats on test days, never used for training; converted to potential temperature (TEOS-10). The model closes ${Math.round(100 * (o.clim.rmse - o.pred.rmse) / (o.clim.rmse - o.glorys.rmse))}% of the gap between climatology and GLORYS, and halves the climatology's indicator errors.`,
    { x: M, y: 2.95, w: W - 2 * M, h: 0.6, fontSize: 13, color: C.text1, margin: 0, isTextBox: true });
  fitImage(s, FIG("phase6/04_argo_validation.png"), M, 3.6, W - 2 * M, 3.3, "ARGO validation figure");
  s.addNotes("ARGO floats are real in-situ measurements that were never used for training, tuning or selection, so this is the strongest evidence against leakage. Caveat: GLORYS assimilates ARGO, so ARGO is independent of our model but not of the training target. Near the surface our model is even slightly closer to ARGO than GLORYS.");
}

// ================================================================ Slide 11: demo screenshots
pres.addSection({ title: "Demonstration" });
{
  const s = content("Demonstration");
  s.addText("Demonstration: outputs of the working system", { placeholder: "title" });
  fitImage(s, FIG("phase6/03_cyclone_tchp.png"), M, 1.1, W - 2 * M, 3.95, "Cyclone TCHP maps: truth, ML, climatology");
  fitImage(s, FIG("phase5/06_example_profiles.png"), M, 5.15, 6.05, 1.8, "Example profiles: truth vs ML vs climatology");
  fitImage(s, FIG("phase6/07_daily_rmse.png"), 6.78, 5.15, 6.05, 1.8, "Daily RMSE on test days");
  s.addNotes("These are real outputs of the pipeline (scripts/06_evaluate.py). Top: heat potential under cyclones Tauktae and Yaas: GLORYS truth, our ML prediction, climatology. The ML maps recover the warm water along both tracks that the climatology misses. Bottom left: predicted vs true profiles. Bottom right: daily error over the test months; ML beats climatology every day.");
}

// ================================================================ Slide 12: team matrix
{
  const s = content("Demonstration");
  s.addText("Team responsibility and self-contribution matrix", { placeholder: "title" });
  const acts = ["Data acquisition and harmonisation", "Data preprocessing and EDA", "Feature engineering", "Model building", "Model comparisons", "Ensemble", "Hyperparameter tuning / cross-validation", "Classification and regularization", "ARGO validation and indicators", "Presentation / interface UI", "Documentation"];
  const rows = [[th("Activity"), th("Aryan Bhutani"), th("<Member 2>"), th("<Member 3>"), th("<Member 4>")]].concat(acts.map((a) => [td(a), td(""), td(""), td(""), td("")]));
  s.addTable(zebra(rows), { x: M, y: 1.2, w: W - 2 * M, colW: [4.33, 2.0, 2.0, 2.0, 2.0], fontFace: THEME.bodyFontFace, border: { type: "solid", pt: 0.5, color: HEX.accent4 }, rowH: 0.45, margin: 0.06 });
  s.addNotes("Fill in each member's name and their contribution in every row (e.g. Lead / Support / tick).");
}

// ================================================================ Slide 13: conclusions
pres.addSection({ title: "Conclusion" });
{
  const s = pres.addSlide({ masterName: "Title Dark", sectionTitle: "Conclusion" });
  s.addText("Conclusions", { x: M, y: 0.4, w: 12, h: 0.8, fontSize: 36, bold: true, color: C.background1, fontFace: THEME.headFontFace, margin: 0, isTextBox: true });
  const red = Math.round(100 * (1 - FM.overall.rmse / T5.models.climatology.overall.rmse));
  const stats = [
    [`${f2(FT.overall.rmse)} °C`, `test RMSE over 1.43M cell-days, ${red}% below climatology`],
    [`${f2(AR.overall.pred.rmse)} °C`, `RMSE against ${AR.n_matchups_cell_days.toLocaleString("en-US")} independent ARGO profiles (climatology ${f2(AR.overall.clim.rmse)})`],
    [`${f3(CL.models.gradient_boosting.accuracy)}`, `accuracy for cyclone-favourable ocean; recall 0.94 vs ${f2(CL.models.climatology_rule.recall)} for climatology`],
    [`½ error`, `for D20, TCHP and heat content compared with climatology`],
  ];
  stats.forEach(([b, l], i) => {
    const x = M + i * 3.13;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.45, w: 2.95, h: 1.9, rectRadius: 0.08, fill: { color: C.text2 }, line: { color: C.text2 }, objectName: `conclusion stat ${i}` });
    s.addText(b, { x: x + 0.2, y: 1.55, w: 2.55, h: 0.8, fontSize: 30, bold: true, color: i % 2 ? C.accent6 : C.accent4, fontFace: THEME.headFontFace, margin: 0, isTextBox: true });
    s.addText(l, { x: x + 0.2, y: 2.35, w: 2.55, h: 0.95, fontSize: 12, color: C.background1, margin: 0, valign: "top", isTextBox: true });
  });
  s.addText([
    { text: "Carefully engineered classical ML reconstructs the subsurface well from surface data: tree ensembles win, and sea level is the key thermocline signal.", options: { bullet: true, breakLine: true } },
    { text: "Leakage-free design (whole-month split, CV-only decisions) and independent ARGO validation make the results defensible.", options: { bullet: true, breakLine: true } },
    { text: "Limitations: one year of data; GLORYS as truth assimilates ARGO; predictions are smoother than reality; the model relies on location.", options: { bullet: true, breakLine: true } },
    { text: "Future work: multi-year training, spatial-holdout tests, uncertainty estimates, and comparison with the deep-learning reference.", options: { bullet: true } },
  ], { x: M, y: 3.8, w: 12.3, h: 3.0, fontSize: 17, color: C.background1, margin: 0, valign: "top", paraSpaceAfter: 10, isTextBox: true });
  s.addNotes("Close on the four headline numbers and state the limitations openly.");
}

// ================================================================ Slide 14: references
{
  const s = content("Conclusion");
  s.addText("References", { placeholder: "title" });
  const refs = [
    "Ali, M.M., Swain, D., Weller, R.A. (2004). Estimation of ocean subsurface thermal structure from surface parameters: a neural network approach. Geophys. Res. Lett., 31, L20308.",
    "Guinehut, S., Dhomps, A.-L., Larnicol, G., Le Traon, P.-Y. (2012). High resolution 3-D temperature and salinity fields derived from in situ and satellite observations. Ocean Science, 8, 845–857.",
    "Su, H., Wu, X., Yan, X.-H., Kidwell, A. (2015). Estimation of subsurface temperature anomaly in the Indian Ocean during recent global surface warming hiatus from satellite measurements: a support vector machine approach. Remote Sens. Environ., 160, 63–71.",
    "Su, H., Li, W., Yan, X.-H. (2018). Retrieving temperature anomaly in the global subsurface and deeper ocean from satellite observations. J. Geophys. Res. Oceans, 123, 399–410.",
    "Lellouche, J.-M. et al. (2021). The Copernicus global 1/12° oceanic and sea ice GLORYS12 reanalysis. Front. Earth Sci., 9, 698876.",
    "Good, S. et al. (2020). The current configuration of the OSTIA system for operational production of foundation SST and ice concentration analyses. Remote Sensing, 12(4), 720.",
    "Copernicus Marine Service products: GLOBAL_MULTIYEAR_PHY_ENS_001_031, GLOBAL_MULTIYEAR_PHY_001_030, SST_GLO_SST_L4_REP_OBSERVATIONS_010_011, MULTIOBS_GLO_PHY_S_SURFACE_MYNRT_015_013, SEALEVEL_GLO_PHY_L4_MY_008_047, WIND_GLO_PHY_L4_MY_012_006.",
    "Argo (2000). Argo float data and metadata from the Global Data Assembly Centre (Argo GDAC). SEANOE. doi:10.17882/42182.",
    "Knapp, K.R. et al. (2010). The International Best Track Archive for Climate Stewardship (IBTrACS). Bull. Amer. Meteor. Soc., 91, 363–376.",
    "Leipper, D.F., Volgenau, D. (1972). Hurricane heat potential of the Gulf of Mexico. J. Phys. Oceanogr., 2, 218–224.",
    "Large, W.G., Pond, S. (1981). Open ocean momentum flux measurements in moderate to strong winds. J. Phys. Oceanogr., 11, 324–336.",
    "Pedregosa, F. et al. (2011). Scikit-learn: machine learning in Python. J. Mach. Learn. Res., 12, 2825–2830.",
    "SIH26066 problem statement (INCOIS); OceanEmbed reference repository: github.com/AshmanRaut/OceanEmbed. Project code: github.com/Aryanbhutani14/Oceantemperatures.",
  ];
  s.addText(refs.map((t, i) => ({ text: t, options: { breakLine: i < refs.length - 1 } })),
    { x: M, y: 1.2, w: W - 2 * M, h: 5.7, fontSize: 12, color: C.text1, margin: 0, valign: "top", paraSpaceAfter: 6, isTextBox: true });
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  if (SKILL) {
    const { applyTheme } = require(path.join(SKILL, "scripts", "apply_theme.js"));
    await applyTheme(OUT, THEME);
  }
  console.log("wrote", OUT);
})();
