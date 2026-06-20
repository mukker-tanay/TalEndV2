---
name: run-harness
description: Run the standalone CV-parsing QC harnesses (name + non-name fields) and the accuracy score mode. Use when measuring parser accuracy/coverage, regenerating labeling sheets, or validating a parsing change before productionizing.
---

# Run the CV-parsing QC harnesses

All commands run from `BackEnd/`. The harnesses are standalone (import nothing from `app/`).
PDF text uses pdfminer (slow) — full-set runs over `uploaded_cvs/test` take a couple minutes;
prefer `run_in_background` for the full set.

## Non-name fields (company / designation / experience / skills) — `qc_fields_eval.py`

- Coverage on a sample: `python qc_fields_eval.py --dir uploaded_cvs/test --limit 80 --show 0`
- Detailed per-CV output: `python qc_fields_eval.py --dir uploaded_cvs/test --limit 30 --show 30`
- **Accuracy vs hand labels:** `python qc_fields_eval.py --dir uploaded_cvs/test --truth fields_truth.csv`
  - Reports per-field recall/precision split by confidence tier (high/medium/none). Gate rule: accept `high`, route the rest to Gemini.
- Regenerate the labeling sheet (openable paths + blank `*_TRUE` cols): `python qc_fields_eval.py --dir uploaded_cvs/test --limit 240 --show 0 --csv fields_labels.csv`

Truth labels live in `BackEnd/fields_truth.csv` (file, company_TRUE, designation_TRUE, experience_TRUE).

## Name — `qc_name_eval.py`

- `python qc_name_eval.py eval --dir uploaded_cvs --labels labels.csv --pdf-engine pdfminer [--no-gemini]`
- `python qc_name_eval.py autolabel --dir uploaded_cvs --out labels.csv` (then eyeball noisy rows)

## Notes

- Some local envs are missing app-only deps (e.g. `sentry_sdk`); the harnesses don't need them. To test the *production* path (`parse_cv_enhanced`), use the repo-root `.venv` and install any missing deps locally — never edit `app/` to make a harness run.
- Coverage ≠ accuracy: always check the empty-label count before trusting a score run (a bad autolabel silently tanks every method).
