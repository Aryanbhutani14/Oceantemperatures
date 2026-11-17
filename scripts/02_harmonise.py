"""Phase 2 - harmonise every source onto the canonical grid (pass --source <name>|all)

Thin command-line wrapper; the logic lives in src/ (pip install -e .).
"""
import runpy
import sys

MODULES = ['oceanembed_ml.data.harmonise']

if __name__ == "__main__":
    for m in MODULES:
        print(f"==> python -m {m} {' '.join(sys.argv[1:])}", flush=True)
        runpy.run_module(m, run_name="__main__")
