"""Phase 7 - classification (TCHP >= 60 kJ cm-2) + regularization validation curves.

    python scripts/07_classification.py
Thin wrapper; logic in src/oceanembed_ml/classification/ and models/regularization.py.
"""
import runpy

if __name__ == "__main__":
    for m in ("oceanembed_ml.classification.train_eval", "oceanembed_ml.models.regularization"):
        print(f"==> python -m {m}", flush=True)
        runpy.run_module(m, run_name="__main__")
