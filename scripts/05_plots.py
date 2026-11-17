"""Phase 5 - figures from results/phase5/*.json (run after 05_models.py and 05_ablation.py)."""
import runpy

if __name__ == "__main__":
    runpy.run_module("oceanembed_ml.viz.phase5", run_name="__main__")
