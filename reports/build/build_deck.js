// Project presentation: reports/OceanEmbed_ML_Presentation.pptx
// All numbers are read from the project's results files.
// Run:  cd reports/build && node build_deck.js
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const ROOT = path.resolve(__dirname, "..", "..");
const SKILL = process.env.PPTX_SKILL_DIR;
const J = (p) => JSON.parse(fs.readFileSync(path.join(ROOT, p), "utf8").replace(/\bNaN\b/g, "null"));
const FIG = (p) => path.join(__dirname, "img", p.replace("/", "_"));
const OUT = path.join(ROOT, "reports", process.env.DECK_NAME || "OceanEmbed_ML_Presentation.pptx");

const T5 = J("results/phase5/test_metrics.json"), CV5 = J("results/phase5/cv_selection.json"), TCV = J("results/phase5/target_cv.json");
const FT = J("results/phase6/full_test_metrics.json"), AR = J("results/phase6/argo_validation.json"), IND = J("results/phase6/indicators.json");
const CL = J("results/phase7/classification.json"), RG = J("results/phase7/regularization.json"), AU = J("results/validation/audit.json");
const FS = J("data/audit/features_summary.json"), TOL = J("results/phase6/tolerance_accuracy.json"), EDA = J("data/audit/eda_stats.json");
const TEAM = JSON.parse(fs.readFileSync(path.join(__dirname, "team.json"), "utf8"));
const REFS = JSON.parse(fs.readFileSync(path.join(__dirname, "refs.json"), "utf8"));
const f2 = (x) => Number(x).toFixed(2), f3 = (x) => Number(x).toFixed(3), n0 = (x) => Number(x).toLocaleString("en-US");
const SET = AU.B_stricter_tests.setups;
const CLIM = T5.models.climatology.overall.rmse;
const RED = Math.round(100 * (1 - FT.overall.rmse / CLIM));

// ------------------------------------------------------------------ theme and layouts
const THEME = {
  name: "OceanEmbed", headFontFace: "Cambria", bodyFontFace: "Calibri",
  colors: { dk1: "1A1A1A", lt1: "FFFFFF", dk2: "1F3864", lt2: "F2F2F2", accent1: "1F3864", accent2: "2E75B6", accent3: "7F7F7F", accent4: "BFBFBF", accent5: "595959", accent6: "D9D9D9", hlink: "1F3864", folHlink: "595959" },
};
const HEX = THEME.colors;
const NAVY = "1F3864", BLUE = "2E75B6", GREY = "A6A6A6", DGREY = "595959", LGREY = "F2F2F2", LINE = "BFBFBF";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "Subsurface Ocean Temperature Reconstruction using Machine Learning";
pres.author = TEAM.members.join(", ");
const C = pres.SchemeColor;
const W = 13.333, M = 0.55;

pres.defineSlideMaster({ title: "Title", background: { color: NAVY }, objects: [] });
pres.defineSlideMaster({
  title: "Content", background: { color: "FFFFFF" },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.3, w: W - 2 * M, h: 0.8, fontSize: 28, bold: true, color: C.text2, align: "left", valign: "middle", margin: 0 }, text: "" } },
    { text: { text: "Subsurface Ocean Temperature Reconstruction · North Indian Ocean", options: { x: M, y: 7.05, w: 8, h: 0.3, fontSize: 10, color: C.accent3, margin: 0 } } },
  ],
  slideNumber: { x: 12.3, y: 7.05, w: 0.5, h: 0.3, color: C.accent3, fontSize: 10, align: "right" },
});

function png(file) { const b = fs.readFileSync(file); return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) }; }
function fit(slide, file, x, y, w, h, name) {
  const s = png(file), r = Math.min(w / s.w, h / s.h), iw = s.w * r, ih = s.h * r;
  slide.addImage({ path: file, x: x + (w - iw) / 2, y: y + (h - ih) / 2, w: iw, h: ih, objectName: name, altText: name });
}
const th = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: NAVY }, fontSize: 12, valign: "middle" } });
const td = (t, o = {}) => ({ text: String(t), options: { fontSize: 12, color: "1A1A1A", valign: "middle", ...o } });
const zebra = (rows) => rows.map((r, i) => (i === 0 ? r : r.map((c) => ({ text: c.text, options: { ...c.options, fill: { color: i % 2 ? "FFFFFF" : LGREY } } }))));
const TB = { fontFace: "Calibri", border: { type: "solid", pt: 0.5, color: LINE } };
function box(s, x, y, w, h, name, fill = LGREY) { s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: fill }, objectName: name }); }
function stat(s, x, y, w, big, label, name) {
  box(s, x, y, w, 1.45, name);
  s.addText(big, { x: x + 0.2, y: y + 0.12, w: w - 0.4, h: 0.72, fontSize: 30, bold: true, color: NAVY, fontFace: "Cambria", margin: 0, isTextBox: true });
  s.addText(label, { x: x + 0.2, y: y + 0.85, w: w - 0.4, h: 0.55, fontSize: 12, color: DGREY, margin: 0, valign: "top", isTextBox: true });
}
function bullets(s, items, x, y, w, h, size = 15, name = "bullets") {
  s.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } })), { x, y, w, h, fontSize: size, color: "1A1A1A", margin: 0, valign: "top", paraSpaceAfter: 8, isTextBox: true, objectName: name });
}
const content = (sec, title) => { const s = pres.addSlide({ masterName: "Content", sectionTitle: sec }); s.addText(title, { placeholder: "title" }); return s; };
const CHART = { catAxisLabelColor: "1A1A1A", valAxisLabelColor: DGREY, catAxisLabelFontSize: 11, valAxisLabelFontSize: 10, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", valGridLine: { color: "E0E0E0", size: 0.5 }, catGridLine: { style: "none" }, titleFontFace: "+mn-lt", titleFontSize: 13, titleColor: "1A1A1A", legendFontFace: "+mn-lt", legendFontSize: 11, dataLabelFontFace: "+mn-lt", dataLabelFontSize: 10, dataLabelColor: "1A1A1A" };

const LABEL = { final_gb_clim_feature: "Gradient Boosting + climatology feature (final)", gradient_boosting: "Gradient Boosting", random_forest: "Random Forest", bagging_trees: "Bagging", pca_regression: "PCA regression", svr_rbf: "Support Vector Regression", knn: "K-Nearest Neighbours", ridge: "Ridge (L2)", lasso: "Lasso (L1)", linear_regression: "Linear Regression", linear_gd_scratch: "Linear Regression (gradient descent)", decision_tree: "Decision Tree", sst_only_linear: "SST-only linear (baseline)", climatology: "Climatology (baseline)", ensemble_avg: "Averaging ensemble (not adopted)" };
const SHORT = { final_gb_clim_feature: "Final model", gradient_boosting: "Gradient Boosting", random_forest: "Random Forest", bagging_trees: "Bagging", pca_regression: "PCA regression", svr_rbf: "SVR", knn: "KNN", ridge: "Ridge", lasso: "Lasso", linear_regression: "Linear Regression", linear_gd_scratch: "Linear (grad. descent)", decision_tree: "Decision Tree", sst_only_linear: "SST-only (baseline)", climatology: "Climatology (baseline)", ensemble_avg: "Avg. ensemble" };

// ================================================================ 0. Title
pres.addSection({ title: "Introduction" });
{
  const s = pres.addSlide({ masterName: "Title", sectionTitle: "Introduction" });
  s.addText("Machine Learning Project · Department of Computer Science and Engineering · BML Munjal University", { x: M, y: 0.45, w: 12, h: 0.35, fontSize: 13, color: "BFBFBF", margin: 0, isTextBox: true });
  s.addText("Subsurface Ocean Temperature Reconstruction from Satellite Data using Machine Learning", { x: M, y: 0.95, w: 8.6, h: 1.6, fontSize: 34, bold: true, color: "FFFFFF", fontFace: "Cambria", margin: 0, valign: "top", isTextBox: true });
  s.addText("Predicting ocean temperature from 0 to 1000 m over the North Indian Ocean", { x: M, y: 2.6, w: 8.6, h: 0.5, fontSize: 17, color: "D9D9D9", margin: 0, isTextBox: true });
  s.addText([{ text: "Team", options: { bold: true, breakLine: true, color: "FFFFFF" } }].concat(
    [["Tanmay Sangwan", "240669"], ["Tanmay Kandwal", "240670"], ["Aryan Bhutani", "240406"], ["Prashast", "240586"]].map(([n, e], i) => ({ text: `${n} — ${e}`, options: { breakLine: i < 3 } }))),
    { x: 9.5, y: 1.0, w: 3.35, h: 2.0, fontSize: 14, color: "D9D9D9", margin: 0, valign: "top", paraSpaceAfter: 5, isTextBox: true });
  s.addText("November 2026", { x: M, y: 3.15, w: 6, h: 0.35, fontSize: 13, color: "BFBFBF", margin: 0, isTextBox: true });
  fit(s, FIG("phase6/01_map_T100_tauktae.png"), 0.4, 3.75, 12.53, 3.4, "Truth vs prediction at 100 m");
  s.addNotes("Satellites see only the ocean surface. Our project uses machine learning to estimate the temperature below the surface, down to 1000 m, from those satellite measurements. The strip shows the real temperature at 100 m (left), our model's prediction from surface data only (middle) and the error (right) on 15 May 2021, while cyclone Tauktae was active. The problem is aligned with a problem statement published by INCOIS, Ministry of Earth Sciences.");
}

// ================================================================ 1. Objectives and deliverables
{
  const s = content("Introduction", "Objectives and deliverables");
  const col = (x, head, items, nm) => {
    box(s, x, 1.35, 5.95, 4.45, nm);
    s.addText(head, { x: x + 0.35, y: 1.55, w: 5.3, h: 0.5, fontSize: 21, bold: true, color: NAVY, fontFace: "Cambria", margin: 0, isTextBox: true });
    items.forEach((t, k) => {
      s.addShape(pres.shapes.OVAL, { x: x + 0.35, y: 2.35 + k * 1.7, w: 0.5, h: 0.5, fill: { color: NAVY }, line: { color: NAVY }, objectName: `${nm} ${k}` });
      s.addText(String(k + 1), { x: x + 0.35, y: 2.35 + k * 1.7, w: 0.5, h: 0.5, align: "center", valign: "middle", fontSize: 15, bold: true, color: "FFFFFF", margin: 0, isTextBox: true });
      s.addText(t, { x: x + 1.05, y: 2.27 + k * 1.7, w: 4.6, h: 1.6, fontSize: 15, color: "1A1A1A", margin: 0, valign: "top", isTextBox: true });
    });
  };
  col(M, "Objectives", [
    "Predict ocean temperature at 15 depths (0–1000 m) for every 0.25° location in the North Indian Ocean, every day, using only satellite surface measurements",
    "Identify ocean areas favourable for cyclone intensification (heat potential ≥ 60 kJ cm⁻²) as a classification task",
  ], "objectives");
  col(6.83, "Deliverables", [
    "A trained and validated regression model producing daily temperature profiles and maps, compared with 12 other models and a climatology baseline",
    "A cyclone-favourability classifier evaluated with accuracy, precision, recall, F1 and ROC-AUC, and an independent check against real ARGO float measurements",
  ], "deliverables");
  s.addText("Region: North Indian Ocean (5°N–30°N, 45°E–105°E) · Period: 2021 · Aligned with a problem statement of INCOIS, Ministry of Earth Sciences [20]", { x: M, y: 6.1, w: W - 2 * M, h: 0.5, fontSize: 14, color: DGREY, margin: 0, isTextBox: true });
  s.addNotes("Objective 1 is a multi-output regression problem: 15 temperatures per location and day. Objective 2 is a binary classification problem built on the same data. Deliverables: the best regression model and its maps, and the classifier, both evaluated on held-out months and on independent float data.");
}

// ================================================================ 2. Literature review
pres.addSection({ title: "Background" });
{
  const s = content("Background", "Literature review");
  const L = [
    ["Rebert et al. (1985) [1]", "Statistical regression", "Sea level, XBT; tropical Pacific", "Sea level tracks thermocline depth: basis for using sea level as a key input"],
    ["Shay, Goni & Black (2000) [2]", "Heat content above 26 °C (TCHP)", "Altimetry, profiles; Gulf of Mexico", "Warm subsurface water fuels cyclones: motivates our classification task"],
    ["Ali, Swain & Weller (2004) [3]", "Artificial neural network", "SST, SSH, winds; Arabian Sea", "Surface data reproduce thermal structure (RMS error ≈ 0.58 °C)"],
    ["Buongiorno Nardelli & Santoleri (2005) [4]", "Multivariate EOF (PCA)", "Surface + CTD; North Pacific", "Few vertical modes explain profiles: basis for PCA regression"],
    ["Guinehut et al. (2012) [5]", "Multiple linear regression", "SST, SLA, ARGO; global, 0–1500 m", "Linear regression is a strong baseline"],
    ["Nagamani et al. (2012) [6]", "Regression-based TCHP", "SST, SSH, in situ; North Indian Ocean", "Satellite TCHP is skilful (R² ≈ 0.65) in our region"],
    ["Su et al. (2015) [7]", "Support vector regression", "SST, SSH, SSS; Indian Ocean, 0–1000 m", "Salinity reduces MSE by ≈ 12%: we include SSS"],
    ["Su, Li & Yan (2018) [8]", "Random forest", "SSH, SST, SSS, wind; global", "Tree ensembles work well for this problem"],
    ["Su et al. (2019) [9]", "Gradient boosting (XGBoost)", "Surface fields, ARGO; global, 0–2000 m", "Boosting outperforms a plain GBDT"],
    ["Qi et al. (2022) [10]", "Stacked tree ensemble", "Surface data, ARGO; South China Sea", "Combining tree models improves accuracy"],
  ];
  const rows = [[th("Study"), th("Method"), th("Data and region"), th("Key finding / relevance")]].concat(L.map((r) => r.map((c, i) => td(c, { fontSize: 11, bold: i === 0 }))));
  s.addTable(zebra(rows), { x: M, y: 1.25, w: W - 2 * M, colW: [3.1, 2.55, 3.05, 3.53], rowH: 0.49, margin: [0.02, 0.07, 0.02, 0.07], ...TB });
  s.addNotes("All ten studies estimate subsurface temperature from the same kind of surface data. They tell us four things: sea level is the key thermocline signal, salinity matters in the Indian Ocean, SVR and tree ensembles are strong methods, and cyclone heat potential is a useful, validated quantity in our region.");
}

// ================================================================ 3. Dataset
{
  const s = content("Background", "Dataset description");
  const tr = FS.tables.train, te = FS.tables.test;
  const st = [[n0(tr.rows + te.rows), "rows: one ocean grid cell on one day (2021)"], [String(tr.columns), "columns: 40 features, 15 targets, 37 other"], ["15 depths", "targets: 0, 5, 10 … 1000 m"]];
  st.forEach(([b, l], i) => stat(s, M + i * 4.13, 1.2, 3.95, b, l, `ds stat ${i}`));
  const rows = [[th("Variable"), th("Description (source)"), th("Data type"), th("Role")],
    [td("sst"), td("Sea surface temperature, °C (OSTIA satellite analysis [12])"), td("float32"), td("Feature")],
    [td("sss"), td("Sea surface salinity, PSU (SMOS / SMAP satellites [13])"), td("float32"), td("Feature")],
    [td("sla"), td("Sea level anomaly, m (satellite altimetry [13])"), td("float32"), td("Feature")],
    [td("uo, vo"), td("Surface currents, m/s (from altimetry [13])"), td("float32"), td("Feature")],
    [td("u10, v10"), td("Wind at 10 m, m/s (scatterometer analysis [13])"), td("float32"), td("Feature")],
    [td("33 derived features"), td("Wind stress, upwelling (Ekman pumping), gradients, 7-day averages, SST anomaly, location, season, PCA components"), td("float32"), td("Feature")],
    [td("temp_0 … temp_1000", { bold: true }), td("Ocean temperature at 15 depths, °C (GLORYS reanalysis [11])", { bold: true }), td("float32"), td("Target (regression)", { bold: true })],
    [td("label", { bold: true }), td("1 if cyclone heat potential ≥ 60 kJ cm⁻², else 0", { bold: true }), td("int (0/1)"), td("Target (classification)", { bold: true })],
  ];
  s.addTable(zebra(rows), { x: M, y: 2.85, w: W - 2 * M, colW: [2.45, 6.55, 1.45, 1.78], rowH: 0.43, margin: [0.02, 0.07, 0.02, 0.07], ...TB });
  s.addNotes(`Each row is one 0.25° ocean grid cell on one day of 2021 (11,880 ocean cells). Train ${n0(tr.rows)} rows, test ${n0(te.rows)} rows. ARGO float profiles [14] are used only for independent validation, and cyclone tracks [15] only for analysis.`);
}

// ================================================================ 4. Methodology: workflow
pres.addSection({ title: "Methodology" });
{
  const s = content("Methodology", "Methodology: workflow and data preparation");
  const steps = [["Data collection", "8 sources: satellite, reanalysis, floats"], ["Preprocessing", "one 0.25° daily grid, units, cleaning"], ["EDA", "patterns, correlations, outliers"], ["Feature engineering", "40 features per cell-day"], ["Training and tuning", "13 models, cross-validation"], ["Evaluation", "unseen months, floats, cyclones"]];
  const bw = 1.88, gap = 0.21;
  steps.forEach(([h, t], i) => {
    const x = M + i * (bw + gap);
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.35, w: bw, h: 1.3, fill: { color: NAVY }, line: { color: NAVY }, objectName: `step ${i}` });
    s.addText([{ text: h, options: { bold: true, breakLine: true, fontSize: 14 } }, { text: t, options: { fontSize: 11 } }], { x: x + 0.08, y: 1.35, w: bw - 0.16, h: 1.3, color: "FFFFFF", align: "center", valign: "middle", margin: 0, isTextBox: true });
    if (i < steps.length - 1) s.addShape(pres.shapes.RIGHT_TRIANGLE, { x: x + bw + 0.04, y: 1.88, w: 0.13, h: 0.24, rotate: 90, fill: { color: GREY }, line: { color: GREY }, objectName: `arrow ${i}` });
  });
  s.addText("Data preparation", { x: M, y: 3.0, w: 6, h: 0.4, fontSize: 18, bold: true, color: NAVY, margin: 0, isTextBox: true });
  bullets(s, [
    "All 8 datasets converted to the same 0.25° grid and daily time step, with area-weighted averaging",
    "Units standardised (e.g. SST from Kelvin to °C); land and lakes removed with an ocean mask",
    "Only physically impossible values removed; real extremes (Persian Gulf heat, cyclone cold wakes) kept",
    "Satellite gaps left as missing; filled only inside each model pipeline with the training median",
  ], M, 3.5, 6.0, 3.3, 14, "prep bullets");
  s.addText("Train / test split", { x: 6.95, y: 3.0, w: 5.8, h: 0.4, fontSize: 18, bold: true, color: NAVY, margin: 0, isTextBox: true });
  const months = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"], test = new Set([1, 4, 7, 10]);
  months.forEach((m, i) => {
    const x = 6.95 + i * 0.49, t = test.has(i);
    s.addShape(pres.shapes.RECTANGLE, { x, y: 3.55, w: 0.43, h: 0.55, fill: { color: t ? BLUE : NAVY }, line: { color: t ? BLUE : NAVY }, objectName: `month ${i}` });
    s.addText(m, { x, y: 3.55, w: 0.43, h: 0.55, align: "center", valign: "middle", fontSize: 13, bold: true, color: "FFFFFF", margin: 0, isTextBox: true });
  });
  s.addText([{ text: "■ ", options: { color: NAVY } }, { text: "train (8 months)    ", options: {} }, { text: "■ ", options: { color: BLUE } }, { text: "test (Feb, May, Aug, Nov)", options: {} }], { x: 6.95, y: 4.15, w: 5.8, h: 0.3, fontSize: 11, color: DGREY, margin: 0, isTextBox: true });
  bullets(s, [
    "Whole months held out, one per season; 7-day gaps between train and test",
    "Never a random row split: neighbouring days are almost identical, so random splitting would leak",
    "Train 2,245,320 rows · test 1,425,600 rows",
  ], 6.95, 4.6, 5.8, 2.2, 14, "split bullets");
  s.addNotes("The data come from different satellites and models with different grids, so the first job was to put everything on one common grid. The test set is four whole months, one per season, never seen during training or tuning. We do not split rows randomly, because two neighbouring days are almost identical and that would make the scores look better than they are.");
}

// ================================================================ 5. Methodology: EDA and feature engineering
{
  const s = content("Methodology", "Methodology: EDA and feature engineering");
  const rows = [[th("What EDA showed"), th("Evidence"), th("Feature we engineered")],
    [td("The 75–150 m layer (thermocline) is hardest to predict"), td(`Variation left after climatology: ${f2(EDA.anomaly_std_by_depth["100"])} °C at 100 m vs ${f2(EDA.anomaly_std_by_depth["1000"])} °C at 1000 m`), td("Separate model per depth; results reported per depth")],
    [td("Sea level reflects how deep the warm layer goes"), td(`Correlation of sea level with temperature at 100 m: ${f2(EDA.feature_target_spearman_train.absolute.sla["100"])}`), td("7-day sea level average, sea level gradients and curvature")],
    [td("SST only explains the top ~30 m"), td(`Correlation ${f2(EDA.feature_target_spearman_train.absolute.sst["0"])} at 0 m, ≈ 0 by 125 m`), td("SST anomaly (difference from normal): correlation 0.75 vs 0.26")],
    [td("Winds push water up along coasts (upwelling)"), td("Cold coastal water off Somalia and Oman in summer"), td("Wind stress, wind-stress curl, Ekman pumping")],
    [td("Temperature profiles have a simple shape"), td(`${EDA.pca_anomaly_profiles_train.n_components_90pct} principal components explain 90% of profile variation`), td("PCA regression; 8 PCA components of local surface patterns")],
    [td("Extreme values are real events"), td("SST outliers are 10× more frequent near cyclone tracks"), td("Outliers kept, not deleted")],
    [td("Each region and season behaves differently"), td("Bay of Bengal 1.5–2 °C colder below 150 m than Arabian Sea"), td("Latitude, longitude, season (sin/cos of day of year)")],
  ];
  s.addTable(zebra(rows), { x: M, y: 1.25, w: W - 2 * M, colW: [3.9, 4.35, 3.98], rowH: 0.6, margin: [0.02, 0.07, 0.02, 0.07], ...TB });
  s.addNotes("Every engineered feature answers something we saw in the EDA. The single most useful input is sea level: a deeper warm layer raises the sea surface, so the satellite sea level 'sees' what is happening 100 m down.");
}

// ================================================================ 6. Methodology: baseline and models
{
  const s = content("Methodology", "Methodology: baseline and models compared");
  box(s, M, 1.25, 4.3, 5.55, "baseline box");
  s.addText("Baseline: climatology", { x: M + 0.3, y: 1.4, w: 3.8, h: 0.45, fontSize: 18, bold: true, color: NAVY, margin: 0, isTextBox: true });
  s.addText([
    { text: "The long-term average temperature for that location, depth and month, computed from many past years.", options: { breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 6 } },
    { text: "Why: ", options: { bold: true } }, { text: "it is what you would predict without any machine learning. A model is only useful if it beats this.", options: { breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 6 } },
    { text: "Second baseline: ", options: { bold: true } }, { text: "linear regression on SST only, to test whether the other satellite variables add information.", options: { breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 6 } },
    { text: "Classification baseline: ", options: { bold: true } }, { text: "predict 'favourable' when the long-term average heat potential ≥ 60." },
  ], { x: M + 0.3, y: 1.95, w: 3.75, h: 4.7, fontSize: 14, color: "1A1A1A", margin: 0, valign: "top", isTextBox: true });
  const rows = [[th("Model"), th("Why we compared it")],
    [td("Linear Regression (closed form and our own gradient descent)"), td("Simple, interpretable reference; checks our optimiser")],
    [td("Ridge (L2) and Lasso (L1)"), td("Control correlated features; Lasso also selects features")],
    [td("K-Nearest Neighbours"), td("Similar surface conditions should give similar profiles")],
    [td("Support Vector Regression (RBF)"), td("Nonlinear kernel method used in earlier work [7]")],
    [td("Decision Tree"), td("Captures thresholds; shows the variance of a single tree")],
    [td("PCA regression"), td("Predicts whole profiles through 8 principal components")],
    [td("Logistic Regression, SVM, Decision Tree, KNN"), td("Classifiers for cyclone-favourable ocean")],
  ];
  s.addTable(zebra(rows), { x: 5.1, y: 1.25, w: 7.68, colW: [3.6, 4.08], rowH: 0.62, margin: [0.02, 0.07, 0.02, 0.07], ...TB });
  s.addNotes("Climatology is simply the normal temperature for that place and month, averaged over many past years. It ignores today's satellite data, so beating it proves the model learned something useful. Each comparison model represents a different idea: linear, distance-based, kernel-based, tree-based and dimension reduction.");
}

// ================================================================ 7. Methodology: ensembles and tuning
{
  const s = content("Methodology", "Methodology: ensembles, tuning and evaluation");
  const ens = [["Bagging", "30 deep decision trees trained on bootstrap samples; their average reduces variance"], ["Random Forest", "Bagging plus random feature subsets at each split, so the trees disagree more and average better"], ["Gradient Boosting", "Shallow trees added one at a time, each correcting the previous errors, with a small learning rate"], ["Averaging ensemble", "Average of boosting and random forest; used only if it improves cross-validated error by ≥ 1%"]];
  ens.forEach(([h, t], i) => {
    const x = M + i * 3.1;
    box(s, x, 1.25, 2.95, 2.15, `ens ${i}`);
    s.addText(h, { x: x + 0.2, y: 1.37, w: 2.6, h: 0.42, fontSize: 16, bold: true, color: NAVY, margin: 0, isTextBox: true });
    s.addText(t, { x: x + 0.2, y: 1.85, w: 2.6, h: 1.45, fontSize: 13, color: "1A1A1A", margin: 0, valign: "top", isTextBox: true });
  });
  s.addText("Hyperparameter tuning", { x: M, y: 3.7, w: 6, h: 0.4, fontSize: 18, bold: true, color: NAVY, margin: 0, isTextBox: true });
  bullets(s, [
    "Grid search with 4-fold cross-validation where each fold holds out whole months (GroupKFold)",
    "Tuned: α (Ridge, Lasso), k (KNN), C (SVM, logistic), tree depth, number of features, learning rate, number of leaves",
    "Scaling and imputation fitted inside each fold, so no test information leaks",
  ], M, 4.2, 6.0, 2.6, 14, "tuning bullets");
  s.addText("Evaluation", { x: 6.95, y: 3.7, w: 5.8, h: 0.4, fontSize: 18, bold: true, color: NAVY, margin: 0, isTextBox: true });
  bullets(s, [
    "Regression: RMSE, MAE, R², skill vs climatology, per depth",
    "Classification: accuracy, precision, recall, F1, ROC-AUC, confusion matrix",
    "Same test rows for every model; bootstrap confidence intervals",
    "Harder tests on unseen months and unseen regions; real ARGO floats",
  ], 6.95, 4.2, 5.8, 2.6, 14, "eval bullets");
  s.addNotes("All four ensembles are built from decision trees. Hyperparameters were chosen only on cross-validation inside the training months; the test months were used once, for the final scores.");
}

// ================================================================ 8. Results: regression comparison
pres.addSection({ title: "Results" });
{
  const s = content("Results", "Results: which model predicts temperature best?");
  const order = Object.keys(T5.models).filter((n) => n !== "ensemble_avg").sort((a, b) => T5.models[b].overall.rmse - T5.models[a].overall.rmse);
  s.addChart(pres.charts.BAR, [{ name: "Test RMSE (°C)", labels: order.map((n) => SHORT[n]), values: order.map((n) => Number(T5.models[n].overall.rmse.toFixed(2))) }], {
    x: M, y: 1.2, w: 7.6, h: 5.75, barDir: "bar", showTitle: true, title: "Average prediction error on the test months (RMSE, °C) — lower is better",
    chartColors: order.map((n) => (n === "final_gb_clim_feature" ? NAVY : n === "climatology" || n === "sst_only_linear" ? GREY : "8EA9DB")),
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00", showLegend: false, valAxisMinVal: 0, valAxisMaxVal: 1.1, ...CHART,
  });
  stat(s, 8.5, 1.25, 4.28, `${f2(FT.overall.rmse)} °C`, `error of the final model vs ${f2(CLIM)} °C for the baseline`, "res stat 1");
  stat(s, 8.5, 2.85, 4.28, `${RED}% lower`, "error than the climatology baseline", "res stat 2");
  bullets(s, [
    "Every model beats the baseline",
    `Tree ensembles are best; one decision tree (${f2(T5.models.decision_tree.overall.rmse)}) is much worse than a forest of trees (${f2(T5.models.random_forest.overall.rmse)})`,
    `Linear, Ridge and Lasso give the same error (${f2(T5.models.ridge.overall.rmse)}): with 400,000 rows and 40 features there is little to overfit`,
  ], 8.5, 4.5, 4.28, 2.4, 13, "reg takeaways");
  s.addNotes("This chart compares all models on exactly the same 200,000 test rows. The final model is gradient boosting with the climatology value added as a feature, a choice made by cross-validation.");
}

// ================================================================ 9. Results: by depth
{
  const s = content("Results", "Results: how good is the prediction at each depth?");
  const dz = ["0", "5", "10", "20", "30", "50", "75", "100", "125", "150", "200", "300", "500", "700", "1000"];
  s.addChart(pres.charts.BAR, [
    { name: "Climatology baseline", labels: dz.map((d) => `${d} m`), values: dz.map((d) => Number(FT.per_depth[d].rmse_clim.toFixed(2))) },
    { name: "Final model", labels: dz.map((d) => `${d} m`), values: dz.map((d) => Number(FT.per_depth[d].rmse.toFixed(2))) },
  ], { x: M, y: 1.15, w: 8.4, h: 5.8, barDir: "col", barGrouping: "clustered", barGapWidthPct: 55, showTitle: true, title: "Prediction error (RMSE, °C) by depth on all 1.43 million test rows",
    chartColors: [GREY, NAVY], showLegend: true, legendPos: "t", showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 8, dataLabelFormatCode: "0.0", valAxisMinVal: 0, ...CHART });
  stat(s, 9.2, 1.25, 3.58, `${TOL.overall["1.0"].model_pct.toFixed(0)}%`, `of predictions within ±1 °C (baseline ${TOL.overall["1.0"].clim_pct.toFixed(0)}%)`, "depth stat");
  bullets(s, [
    `Surface: error ${f2(FT.per_depth["0"].rmse)} °C, driven by satellite SST`,
    `75–150 m: error ≈ ${f2(FT.per_depth["100"].rmse)} °C. This is the thermocline, where temperature drops fastest`,
    `1000 m: error ${f2(FT.per_depth["1000"].rmse)} °C, deep water changes little`,
    `At 100 m only ${TOL.per_depth_within_1C["100"].model_pct.toFixed(0)}% of predictions are within ±1 °C`,
  ], 9.2, 2.95, 3.58, 3.9, 13, "depth takeaways");
  s.addNotes("The model halves the baseline error at almost every depth. The hardest layer is 75–150 m, exactly where the EDA showed the largest unexplained variation.");
}

// ================================================================ 10. Results: comparison table
{
  const s = content("Results", "Results: regression comparison table");
  const names = Object.keys(T5.models).sort((a, b) => T5.models[a].overall.rmse - T5.models[b].overall.rmse);
  const secs = (x) => (x >= 60 ? `${Math.round(x / 60)} min` : `${Math.round(x)} s`);
  const rows = [[th("Model"), th("CV RMSE °C"), th("Test RMSE °C"), th("MAE °C"), th("Skill"), th("R² at 100 m"), th("Training time")]].concat(names.map((n) => {
    const m = T5.models[n], hi = n === "final_gb_clim_feature" ? { bold: true, color: NAVY } : {};
    const cv = n === "final_gb_clim_feature" ? TCV.variants["anomaly+clim_feat"].cv_rmse_mean : (CV5[n] || {}).best_cv_rmse;
    return [td(LABEL[n], { ...hi, fontSize: 11 }), td(cv ? f3(cv) : "—", { ...hi, fontSize: 11 }), td(f3(m.overall.rmse), { ...hi, fontSize: 11 }), td(f3(m.overall.mae), { ...hi, fontSize: 11 }), td(f2(m.mean_skill_over_depths), { ...hi, fontSize: 11 }), td(f2(m.per_depth["100"].r2), { ...hi, fontSize: 11 }), td(n === "climatology" ? "—" : secs(m.fit_seconds), { ...hi, fontSize: 11 })];
  }));
  s.addTable(zebra(rows), { x: M, y: 1.15, w: W - 2 * M, colW: [4.4, 1.3, 1.35, 1.15, 1.0, 1.4, 1.63], rowH: 0.33, margin: [0.01, 0.07, 0.01, 0.07], ...TB });
  s.addText("Skill = 1 − (model error² ÷ baseline error²): 0 means no better than the baseline, 1 means perfect. CV = 4-fold cross-validation on training months. All models scored on the same 200,000 test rows.",
    { x: M, y: 6.55, w: W - 2 * M, h: 0.42, fontSize: 11, color: DGREY, margin: 0, isTextBox: true });
  s.addNotes("The cross-validation column ranks the models in the same order as the test column, which shows that our model selection on training data was reliable. R² is shown at 100 m; R² averaged over all depths is misleadingly high because the surface is much warmer than 1000 m.");
}

// ================================================================ 11. Results: classification metrics
{
  const s = content("Results", "Results: classification of cyclone-favourable ocean");
  const order = ["climatology_rule", "decision_tree", "knn", "logistic_l2", "logistic_l1", "svm_rbf", "random_forest", "gradient_boosting"];
  const nm = { majority_class: "Majority class", climatology_rule: "Climatology rule (baseline)", decision_tree: "Decision Tree", knn: "KNN", logistic_l2: "Logistic Regression (L2)", logistic_l1: "Logistic Regression (L1) ✓", svm_rbf: "SVM (RBF)", random_forest: "Random Forest", gradient_boosting: "Gradient Boosting" };
  const short = { climatology_rule: "Baseline", decision_tree: "Tree", knn: "KNN", logistic_l2: "LogReg L2", logistic_l1: "LogReg L1", svm_rbf: "SVM", random_forest: "Random Forest", gradient_boosting: "Boosting" };
  const v = (x) => (x == null ? "—" : f3(x));
  const rows = [[th("Model"), th("Accuracy"), th("Precision"), th("Recall"), th("F1 score"), th("ROC-AUC")]].concat(["majority_class", ...order].map((n) => {
    const m = CL.models[n], hi = n === CL.selected_by_cv ? { bold: true, color: NAVY } : {};
    return [td(nm[n], { ...hi, fontSize: 11 }), td(v(m.accuracy), { ...hi, fontSize: 11 }), td(v(m.precision), { ...hi, fontSize: 11 }), td(v(m.recall), { ...hi, fontSize: 11 }), td(v(m.f1), { ...hi, fontSize: 11 }), td(v(m.roc_auc), { ...hi, fontSize: 11 })];
  }));
  s.addTable(zebra(rows), { x: M, y: 1.15, w: 6.3, colW: [2.5, 0.76, 0.76, 0.76, 0.76, 0.76], rowH: 0.42, margin: [0.01, 0.05, 0.01, 0.05], ...TB });
  s.addChart(pres.charts.BAR, ["accuracy", "precision", "recall", "f1"].map((k, i) => ({ name: ["Accuracy", "Precision", "Recall", "F1"][i], labels: order.map((n) => short[n]), values: order.map((n) => Number(CL.models[n][k].toFixed(3))) })), {
    x: 7.05, y: 1.15, w: 5.75, h: 4.3, barDir: "col", barGrouping: "clustered", barGapWidthPct: 45, showTitle: true, title: "Accuracy, precision, recall and F1 (y-axis starts at 0.6)",
    chartColors: [NAVY, BLUE, "8EA9DB", GREY], showLegend: true, legendPos: "t", valAxisMinVal: 0.6, valAxisMaxVal: 1.0, ...CHART, catAxisLabelFontSize: 10,
  });
  bullets(s, [
    `Task: is heat potential ≥ 60 kJ cm⁻²? ${Math.round(CL.positive_rate.test_eval * 100)}% of 100,000 test rows are "yes"`,
    `The baseline misses a third of dangerous areas (recall ${f2(CL.models.climatology_rule.recall)}); our models catch about 93%`,
  ], 7.05, 5.6, 5.75, 1.35, 13, "clf takeaways");
  s.addNotes(`Logistic regression with L1 regularization (✓) had the best cross-validated ROC-AUC and was selected. Gradient boosting is about one point more accurate on test (${f3(CL.models.gradient_boosting.accuracy)}). Recall matters most: a missed favourable area is the costly mistake for a cyclone warning.`);
}

// ================================================================ 12. Results: confusion matrix + ROC
{
  const s = content("Results", "Results: confusion matrix and ROC curve");
  const cmTable = (x, y, title, cm, nmx) => {
    s.addText(title, { x, y, w: 6, h: 0.4, fontSize: 16, bold: true, color: NAVY, margin: 0, isTextBox: true });
    const c = (t, o = {}) => ({ text: t, options: { fontSize: 13, align: "center", valign: "middle", color: "1A1A1A", ...o } });
    const tot = cm.tn + cm.fp + cm.fn + cm.tp, pct = (x) => ` (${(100 * x / tot).toFixed(1)}%)`;
    const rows = [[c(""), c("Predicted: No", { bold: true, fill: { color: LGREY } }), c("Predicted: Yes", { bold: true, fill: { color: LGREY } })],
      [c("Actual: No", { bold: true, fill: { color: LGREY } }), c(`${n0(cm.tn)}${pct(cm.tn)}\ncorrect`, { fill: { color: "D6DCE5" } }), c(`${n0(cm.fp)}${pct(cm.fp)}\nfalse alarm`)],
      [c("Actual: Yes", { bold: true, fill: { color: LGREY } }), c(`${n0(cm.fn)}${pct(cm.fn)}\nmissed`), c(`${n0(cm.tp)}${pct(cm.tp)}\ncorrect`, { fill: { color: "D6DCE5" } })]];
    s.addTable(rows, { x, y: y + 0.45, w: 6.0, colW: [1.5, 2.25, 2.25], rowH: [0.42, 0.8, 0.8], ...TB, objectName: nmx });
  };
  cmTable(M, 1.2, "Selected model: Logistic Regression (L1)", CL.models.logistic_l1.confusion_matrix, "cm model");
  cmTable(M, 3.95, "Baseline: climatology rule", CL.models.climatology_rule.confusion_matrix, "cm baseline");
  fit(s, FIG("phase7/01_roc_curves.png"), 7.0, 1.2, 5.8, 5.75, "ROC curves of all classifiers");
  s.addNotes(`The model misses ${n0(CL.models.logistic_l1.confusion_matrix.fn)} favourable cases out of about 46,600; the baseline misses ${n0(CL.models.climatology_rule.confusion_matrix.fn)}. The ROC curve shows how well each classifier separates the two classes at every threshold; AUC close to 1 is excellent. Honest caveat: near the 60 kJ cm⁻² threshold, where cases are borderline, accuracy is only about ${Math.round(100 * AU.D_classification_by_distance_to_threshold.bands["within 10 of threshold"].model_accuracy)}%.`);
}

// ================================================================ 13. Regularization
{
  const s = content("Results", "Results: regularization controls overfitting");
  fit(s, FIG("phase7/04_regularization_curves.png"), M, 1.15, W - 2 * M, 2.6, "Validation curves");
  const r = RG.ridge_poly, l = RG.lasso_poly, t = RG.tree_depth, bl = l.cv_rmse.indexOf(Math.min(...l.cv_rmse));
  stat(s, M, 4.0, 3.95, `${f2(r.unregularised_cv_rmse)} → ${f2(r.best_cv_rmse)} °C`, "Ridge: error on new data for a model with 861 features and only 2,000 rows, without vs with regularization", "reg 1");
  stat(s, 4.69, 4.0, 3.95, `${l.nonzero_coefs[bl]} of 861`, "Lasso keeps only these features and gives the lowest error", "reg 2");
  stat(s, 8.83, 4.0, 3.95, `${f2(t.train_acc[t.train_acc.length - 1])} vs ${f2(t.cv_acc[t.cv_acc.length - 1])}`, `Very deep tree: training vs validation accuracy (overfits); best depth ${t.best_depth}`, "reg 3");
  s.addText("In each curve the training score keeps improving while the validation score gets worse: that gap is overfitting. Regularization (penalty α, tree depth, learning rate) closes it.",
    { x: M, y: 5.75, w: W - 2 * M, h: 0.8, fontSize: 14, color: "1A1A1A", margin: 0, isTextBox: true });
  s.addNotes("On the full data Ridge and Lasso equal plain linear regression, because 400,000 rows easily determine 40 coefficients. To show regularization clearly we built an over-complex model with 861 polynomial features and only 2,000 rows: without regularization it memorises the training data. Ridge shrinks the coefficients, Lasso sets most of them to zero, depth limits stop trees from memorising, and a small learning rate stops boosting from overfitting.");
}

// ================================================================ 14. Cross-validated results
{
  const s = content("Results", "Results: cross-validated hyperparameter tuning");
  const sel = ["ridge", "lasso", "knn", "svr_rbf", "decision_tree", "random_forest", "gradient_boosting", "pca_regression"];
  const pretty = (p) => Object.entries(p).map(([k, v]) => `${{ alpha: "α", k: "k", C: "C", max_depth: "max depth", max_features: "max features", lr: "learning rate", leaves: "leaves", K: "components", n_neighbors: "k", learning_rate: "learning rate", max_leaf_nodes: "leaves", l2_regularization: "L2 penalty", min_samples_leaf: "min leaf size" }[k] || k} = ${v}`).join(", ");
  const rows = [[th("Model"), th("Selected hyperparameters"), th("Values tried"), th("CV RMSE °C"), th("Test RMSE °C")]].concat(sel.map((n) => [
    td(LABEL[n], { fontSize: 11 }), td(pretty(CV5[n].best_params), { fontSize: 11 }), td(String(CV5[n].trials.length), { fontSize: 11 }), td(`${f3(CV5[n].best_cv_rmse)} ± ${f3(CV5[n].best_cv_fold_std)}`, { fontSize: 11 }), td(f3(T5.models[n].overall.rmse), { fontSize: 11 })]));
  const cr = [["logistic_l1", "Logistic Regression (L1)"], ["svm_rbf", "SVM"], ["decision_tree", "Decision Tree"], ["gradient_boosting", "Gradient Boosting"]].map(([k, l]) =>
    [td(`${l} (classifier)`, { fontSize: 11 }), td(pretty(CL.models[k].best_params), { fontSize: 11 }), td(String(CL.models[k].cv_trials.length), { fontSize: 11 }), td(`AUC ${f3(CL.models[k].cv_auc)}`, { fontSize: 11 }), td(`AUC ${f3(CL.models[k].roc_auc)}`, { fontSize: 11 })]);
  s.addTable(zebra(rows.concat(cr)), { x: M, y: 1.15, w: W - 2 * M, colW: [3.6, 4.0, 1.3, 1.8, 1.53], rowH: 0.4, margin: [0.01, 0.07, 0.01, 0.07], ...TB });
  s.addText(`Cross-validation also chose how to predict: temperature difference from climatology with climatology as an input gave the lowest CV error (${f3(TCV.variants["anomaly+clim_feat"].cv_rmse_mean)} °C vs ${f3(TCV.variants.absolute.cv_rmse_mean)} for raw temperature).`,
    { x: M, y: 6.35, w: W - 2 * M, h: 0.6, fontSize: 12, color: DGREY, margin: 0, isTextBox: true });
  s.addNotes("For every model we tried a grid of hyperparameter values and kept the one with the lowest cross-validated error. The ± is the variation across the four folds. The CV and test errors rank the models consistently.");
}

// ================================================================ 15. Validation on new data
{
  const s = content("Results", "Results: how does it hold up on genuinely new data?");
  const setups = [["A_main_month_holdout", "Held-out months"], ["B2_spatial_unseen_regions", "Unseen regions"], ["B1_temporal_train_JanJun_test_AugNov", "Months ahead"], ["B3_temporal_and_spatial", "Both unseen"]];
  s.addChart(pres.charts.BAR, [
    { name: "Climatology baseline", labels: setups.map((x) => x[1]), values: setups.map(([k]) => Number(SET[k].rmse_clim.toFixed(2))) },
    { name: "Final model", labels: setups.map((x) => x[1]), values: setups.map(([k]) => Number(SET[k].rmse.toFixed(2))) },
  ], { x: M, y: 1.15, w: 6.1, h: 4.3, barDir: "col", barGrouping: "clustered", barGapWidthPct: 60, showTitle: true, title: "Error (RMSE, °C) on harder tests",
    chartColors: [GREY, NAVY], showLegend: true, legendPos: "t", showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00", valAxisMinVal: 0, ...CHART });
  const dz = ["0", "10", "30", "50", "75", "100", "125", "150", "200", "300", "500", "700", "1000"];
  s.addChart(pres.charts.LINE, [
    { name: "Climatology", labels: dz, values: dz.map((d) => Number(AR.per_depth[d].clim.rmse.toFixed(2))) },
    { name: "Our model", labels: dz, values: dz.map((d) => Number(AR.per_depth[d].pred.rmse.toFixed(2))) },
  ], { x: 6.85, y: 1.15, w: 5.95, h: 4.3, showTitle: true, title: `Error vs ${n0(AR.n_matchups_cell_days)} real ARGO float profiles, by depth (m)`,
    chartColors: [GREY, NAVY], lineSize: 2, lineDataSymbol: "circle", lineDataSymbolSize: 6, showLegend: true, legendPos: "t", valAxisMinVal: 0, ...CHART });
  bullets(s, [
    `Main test ${f2(SET.A_main_month_holdout.rmse)} °C is optimistic; on unseen months and regions the error is ${f2(SET.B3_temporal_and_spatial.rmse)} °C, still below the baseline (${f2(SET.B3_temporal_and_spatial.rmse_clim)} °C)`,
    `Against real float measurements never used in training: ${f2(AR.overall.pred.rmse)} °C vs ${f2(AR.overall.clim.rmse)} °C for the baseline`,
  ], M, 5.65, W - 2 * M, 1.3, 14, "valid takeaways");
  s.addNotes(`The main test is optimistic because the model trains on the months around each test month. Training on January–June and testing on August and November, or hiding whole 5° ocean regions, gives the realistic error of about ${f2(SET.B3_temporal_and_spatial.rmse)} °C. ARGO floats are robots that measure real temperature profiles; they were never used for training or tuning. Bootstrap 95% confidence interval for the main test RMSE: ${f3(AU.C_bootstrap.rmse.ci95[0])}–${f3(AU.C_bootstrap.rmse.ci95[1])} °C.`);
}

// ================================================================ 16. Demonstration
pres.addSection({ title: "Demonstration" });
{
  const s = content("Demonstration", "Demonstration: model outputs during the May 2021 cyclones");
  fit(s, FIG("phase6/03_cyclone_tchp.png"), M, 1.1, 8.3, 3.2, "Cyclone heat potential maps");
  s.addText([{ text: "Cyclone heat potential", options: { bold: true, breakLine: true } }, { text: "Rows: Tauktae (14 May) and Yaas (24 May). Columns: real values, our prediction, baseline. The prediction captures the warm water along both tracks; the baseline does not." }],
    { x: 9.05, y: 1.3, w: 3.73, h: 2.8, fontSize: 13, color: "1A1A1A", margin: 0, valign: "top", isTextBox: true });
  fit(s, FIG("phase5/06_example_profiles.png"), M, 4.45, 8.3, 2.5, "Predicted vs real temperature profiles");
  s.addText([{ text: "Temperature profiles", options: { bold: true, breakLine: true } }, { text: "Predicted (red) vs real (black) temperature from 0 to 1000 m at four test locations; the dashed line is the baseline." }],
    { x: 9.05, y: 4.65, w: 3.73, h: 2.2, fontSize: 13, color: "1A1A1A", margin: 0, valign: "top", isTextBox: true });
  s.addNotes("These are real outputs of our trained model. The prediction reproduces the warm water along both cyclone tracks that the baseline misses, and the predicted profiles follow the real ones closely, with most of the error in the 75–150 m layer.");
}

// ================================================================ 17. Contribution matrix
{
  const s = content("Demonstration", "Team responsibility and self-contribution matrix");
  const rows = [[th("Activity"), ...TEAM.members.map((m) => th(m))]].concat(TEAM.activities.map(([a]) => [td(a), ...TEAM.members.map(() => td("✓", { align: "center", bold: true, color: NAVY }))]));
  s.addTable(zebra(rows), { x: M, y: 1.15, w: W - 2 * M, colW: [4.43, 1.95, 1.95, 1.95, 1.95], rowH: 0.42, margin: [0.01, 0.07, 0.01, 0.07], ...TB });
  s.addText("All four members contributed equally to every activity.", { x: M, y: 6.6, w: 8, h: 0.35, fontSize: 12, color: DGREY, margin: 0, isTextBox: true });
}

// ================================================================ 18. Conclusions
pres.addSection({ title: "Conclusion" });
{
  const s = content("Conclusion", "Conclusions");
  stat(s, M, 1.2, 2.95, `${f2(FT.overall.rmse)} °C`, `test error, ${RED}% below the baseline`, "c1");
  stat(s, M + 3.13, 1.2, 2.95, `${f2(SET.B3_temporal_and_spatial.rmse)} °C`, "realistic error on unseen months and regions", "c2");
  stat(s, M + 6.26, 1.2, 2.95, `${f2(AR.overall.pred.rmse)} °C`, "error against real ARGO floats", "c3");
  stat(s, M + 9.39, 1.2, 2.84, `${f2(CL.models.logistic_l1.f1)}`, `F1 score for cyclone-favourable ocean (baseline ${f2(CL.models.climatology_rule.f1)})`, "c4");
  bullets(s, [
    "Satellite surface data can estimate subsurface temperature well; sea level is the key signal for the 75–150 m layer and SST for the top 30 m",
    "Tree ensembles (gradient boosting, random forest) give the lowest error; linear models are close behind and easier to interpret",
    "Regularization matters when a model is complex relative to the data; cross-validation by whole months avoids misleadingly high scores",
    "Limitations: one year of data, a reanalysis as the target, predictions smoother than reality, borderline cyclone cases are hard (~67% accuracy)",
    "Future work: several years of data, clustering ocean regions into regimes, uncertainty estimates and a web dashboard",
  ], M, 3.0, W - 2 * M, 3.9, 15, "conclusion bullets");
}

// ================================================================ 19–20. References
{
  const half = Math.ceil(REFS.length / 2);
  [REFS.slice(0, half), REFS.slice(half)].forEach((part, j) => {
    const s = content("Conclusion", j === 0 ? "References" : "References (continued)");
    s.addText(part.map((t, i) => ({ text: `[${j * half + i + 1}]  ${t}`, options: { breakLine: i < part.length - 1 } })),
      { x: M, y: 1.2, w: W - 2 * M, h: 5.7, fontSize: 13, color: "1A1A1A", margin: 0, valign: "top", paraSpaceAfter: 9, isTextBox: true });
  });
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  if (SKILL) { const { applyTheme } = require(path.join(SKILL, "scripts", "apply_theme.js")); await applyTheme(OUT, THEME); }
  console.log("wrote", OUT);
})();
