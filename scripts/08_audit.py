"""Whole-project validation audit: data integrity, stricter tests, bootstrap CIs.

    python scripts/08_audit.py
Thin wrapper; logic in src/oceanembed_ml/validation/audit.py.
"""
import runpy

if __name__ == "__main__":
    runpy.run_module("oceanembed_ml.validation.audit", run_name="__main__")
