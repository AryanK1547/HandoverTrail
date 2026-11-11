# QA Report

## Fixed

- **F1–F2:** Idempotent database bootstrap, persistent demo role selection, landing page, safe upload persistence, and source-scoped parsing are implemented.
- **F3–F4:** Role-required retrieval and review authorization/auditing are implemented; the UI now explains the actual meaning of corroboration.
- **F5–F6:** Gemini and pinned OpenRouter are configured with a labeled heuristic fallback and a per-session limit; an empty database seeds four cached claims with filename/chunk evidence references.
- **F7:** The backend suite passes: **14 passed**. Results are in `qa/results_backend.txt`.
- **F8:** A latest-commit fresh clone started with an empty disposable database. The Reviewer approved a public cached claim; Incoming saw that claim and its three public citations. A separately approved restricted-only claim was hidden, with only an aggregate count of one. The Incoming role persisted across page navigation.
- **F9:** Project, architecture, disclosure, testing, limitations, and Round 3 documentation is included.
- `handovertrail.db` is no longer tracked by Git and matches the `*.db` ignore rule. The local database was preserved; the backup made before the fix phase remains in `%TEMP%`.

## Not fixed

- Roles are simulated, not authenticated.
- Restricted text can be sent to a provider during extraction; filtering is applied at read time.
- Conflict detection, production persistence, real cloud deployment, automated redaction, version history, and acknowledgements are not implemented.
- Streamlit Community Cloud deployment was not tested.

## Evidence

- Backend suite: **14 passed**, recorded in `qa/results_backend.txt`.
- Fresh clone: HTTP 200 / `ok`; empty-database seed, Reviewer approval, Incoming role persistence, three public citations, and one hidden restricted claim observed.
- Legacy database: additive `sensitivity` and `claim_source` migration passed.
- Git: `handovertrail.db` is absent from the index and ignored; the local database was preserved and backed up before the fix phase.

## Delivery

Work was committed on `qa-fixes`; nothing was pushed. Pre-existing unrelated edits to `.streamlit/config.toml`, `requirements.txt`, and `AGENT_QA_BRIEF.md` were left untouched.
