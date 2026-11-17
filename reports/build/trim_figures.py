"""Copy the pipeline figures used in the deck/report with surrounding white margins trimmed."""
from pathlib import Path
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "reports" / "figures"
OUT = Path(__file__).resolve().parent / "img"
FIGS = ["phase6/01_map_T100_tauktae.png", "phase6/03_cyclone_tchp.png", "phase6/04_argo_validation.png", "phase6/07_daily_rmse.png",
        "phase5/06_example_profiles.png", "phase5/01_rmse_skill_by_depth.png", "phase5/02_overall_comparison.png", "phase5/09_ablation.png",
        "phase7/01_roc_curves.png", "phase7/02_confusion_matrices.png", "phase7/04_regularization_curves.png", "phase3/09_feature_target_corr_by_depth.png",
        "phase3/07_profiles_region_season_variance.png", "phase3/01_input_mean_maps.png", "phase2/compare_sst.png", "phase6/06_indicator_scatter.png",
        "phase5/07_gradient_descent.png", "phase3/12_outliers_cyclones.png"]
for f in FIGS:
    im = Image.open(SRC / f).convert("RGB")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    box = ImageChops.difference(im, bg).point(lambda p: 255 if p > 12 else 0).getbbox()
    pad = 12
    if box:
        box = (max(box[0] - pad, 0), max(box[1] - pad, 0), min(box[2] + pad, im.width), min(box[3] + pad, im.height))
        im = im.crop(box)
    dst = OUT / f.replace("/", "_")
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst)
    print(f"{f}: {im.size}")
