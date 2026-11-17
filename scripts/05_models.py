"""Phase 5 - cross-validated model selection + test evaluation of all syllabus models.

    python scripts/05_models.py                       # all models
    python scripts/05_models.py --models ridge knn    # a subset

Thin command-line wrapper; the logic lives in src/oceanembed_ml/models/.
"""
import runpy

if __name__ == "__main__":
    runpy.run_module("oceanembed_ml.models.train_eval", run_name="__main__")
