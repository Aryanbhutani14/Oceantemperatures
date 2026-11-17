"""Phase 5 - ablation studies (feature groups, target, data size, group importance).

Run after scripts/05_models.py (uses the CV-chosen boosting parameters).
Thin command-line wrapper; the logic lives in src/oceanembed_ml/models/ablation.py.
"""
import runpy

if __name__ == "__main__":
    runpy.run_module("oceanembed_ml.models.ablation", run_name="__main__")
