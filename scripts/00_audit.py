"""Phase 0 - dataset audit (catalogues, ARGO index, grid alignment)

Thin command-line wrapper; the logic lives in src/ (pip install -e .).
"""
import runpy
import sys

MODULES = ['oceanembed_ml.audit.cmems', 'oceanembed_ml.audit.podaac_argo', 'oceanembed_ml.audit.grid_alignment']

if __name__ == "__main__":
    for m in MODULES:
        print(f"==> python -m {m} {' '.join(sys.argv[1:])}", flush=True)
        runpy.run_module(m, run_name="__main__")
