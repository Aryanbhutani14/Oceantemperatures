"""Phase 1 - download raw data, then verify.

    python scripts/01_download.py cmems --source all     # glorys, glorys_clim, sst, sss, ssh, winds
    python scripts/01_download.py argo                   # ARGO 2021 profiles + IBTrACS
    python scripts/01_download.py verify                 # checks + SHA-256 manifest

Thin command-line wrapper; the logic lives in src/ (pip install -e .).
"""
import runpy
import sys

TARGETS = {"cmems": "oceanembed_ml.data.download_cmems",
           "argo": "oceanembed_ml.data.download_argo_ibtracs",
           "verify": "oceanembed_ml.data.verify_raw"}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in TARGETS:
        sys.exit(__doc__)
    mod = TARGETS[sys.argv.pop(1)]
    runpy.run_module(mod, run_name="__main__")
