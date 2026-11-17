"""Phase 6 - full-grid test predictions, ARGO validation, ocean indicators, figures.

    python scripts/06_evaluate.py
Thin wrapper; logic in src/oceanembed_ml/{evaluation,validation,science,viz}/.
"""
import runpy

MODULES = ["oceanembed_ml.evaluation.predict_grid",   # all 120 test days x 11,880 cells
           "oceanembed_ml.validation.argo",           # independent ARGO validation
           "oceanembed_ml.science.evaluate",          # D20, D26, TCHP, MLD, OHC300
           "oceanembed_ml.viz.phase6"]                # figures

if __name__ == "__main__":
    for m in MODULES:
        print(f"==> python -m {m}", flush=True)
        runpy.run_module(m, run_name="__main__")
