"""Phase 5 - choose the target formulation by CV, then fit + test the final model.

Run after scripts/05_models.py:
    python scripts/05_final_model.py
Thin wrapper; logic in src/oceanembed_ml/models/{target_cv,final_model}.py.
"""
import runpy

if __name__ == "__main__":
    for m in ("oceanembed_ml.models.target_cv", "oceanembed_ml.models.final_model"):
        print(f"==> python -m {m}", flush=True)
        runpy.run_module(m, run_name="__main__")
