# HandoverTrail System Map

Phase 0 baseline with implementation state and final QA observations through F9, 2026-11-10.

## Runtime and entry points

- The application is a Python/Streamlit multipage app. `app.py` is the landing page; Streamlit discovers scripts under `pages/`.
- The current runtime stack declared in `requirements.txt` is Streamlit, pandas, and `google-genai`.
- The database is SQLite. Its default path is `<project directory>/handovertrail.db`; `HANDOVERTRAIL_DB` can override it. The connection helper enables SQLite foreign-key enforcement.
- The working tree already contains local changes. QA phases must preserve them and must not reset or overwrite the database.

## Implemented data flow

```text
Streamlit Upload Sources page
  ├─ demo files: register names and metadata in `sources`
  └─ custom upload: register names and metadata in `sources`
         │
         ▼
`source_parser.py`
  ├─ reads `.txt` and `.csv` files from `data/demo_project` (or by filename)
  └─ writes source-linked excerpts to `evidence_chunks`
         │
         ▼
Review Claims page → `extractor.py`
  ├─ Gemini (`gemini-3.6-flash`)
  ├─ OpenRouter (`deepseek/deepseek-v4.1-flash-1017`) if Gemini fails
  └─ local keyword heuristic if both AI providers fail
         │
         ▼
`claims` + `claim_evidence`
         │
         ├─ Validate button → `validator.py` updates trust status
         ├─ Admin/Reviewer actions → authorize and audit review records
         └─ Handover page → displays approved claims and linked evidence allowed for Incoming
```

## Component responsibilities and observed boundaries

| Component | Observed responsibility |
|---|---|
| `app.py` | Landing page, workflow summary, demo source loader, and session-persisted role selector. |
| `database.py` | Creates eight SQLite tables, applies additive `sensitivity` and `claim_source` migrations, seeds demo users/project, and on an empty database parses packaged demo sources and seeds cached claims as pending. |
| `source_parser.py` | Validates and persists `.txt`/`.csv` uploads under `uploads/<project>/`; parses UTF-8 BOM or Latin-1 text and ragged CSV rows; reparses only selected or unprocessed sources. Cold-start demo parsing prefers packaged files. |
| `extractor.py` | Builds an evidence prompt, validates returned claim types and evidence IDs, calls Gemini then OpenRouter, and falls back to keyword grouping. Saves generated claims and their evidence links. |
| `validator.py` | Sets `MISSING_EVIDENCE` when no linked evidence exists, `VERIFIED` when linked chunks come from two or more distinct filenames, otherwise `SINGLE_SOURCE`. |
| `permissions.py` | Normalizes simulated role names, checks sensitivity/review capability, and authorizes review writes with review/audit records. |
| `retrieval.py` | Role-required read helpers for visible sources, chunks, claims, claim evidence, and hidden item counts. Incoming claims require approval and every linked source to be public. |
| `models.py` | Empty in the inspected worktree. |
| `pages/1_Upload_Sources.py` | Loads demo sources, persists custom upload bytes with a sensitivity selection, and renders role-visible sources/chunks. |
| `pages/2_Review_Claims.py` | Calls extraction/validation, renders role-visible claims/evidence, and gates approve/reject actions. |
| `pages/3_Handover_View.py` | Renders approved, role-visible claims/citations and an aggregate hidden-item count for Incoming. |

## Schema and QA fixture compatibility

- `sources.sensitivity` is `TEXT NOT NULL DEFAULT 'restricted'`; new databases constrain values to `public` or `restricted`. Existing databases receive an additive column migration.
- The provided QA fixture includes sensitivity labels for public and restricted cases.
- The database has claim trust states including `CONFLICTING`, but the current validator does not detect contradictory claims; it only counts supporting filenames. The UI calls two-or-more-file support “Corroborated.”
- Role selection is simulated in Streamlit session state, not backed by authenticated identity. Incoming reads filter out any claim unless every evidence link is public and the claim is approved. Admin/Reviewer can see public and restricted evidence.
- The synthetic `restricted_demo.txt` contains only an explicitly fake token and fictional example phone number. It is included to check read-time filtering.
- Custom upload bytes are persisted in ignored `uploads/`; parsing searches that per-project directory before packaged demo files.

## Phase 0 observations and risks for later QA

1. **High priority, verify in Phase 1/2:** no automated `tests/` or `qa/` suite was present at initial inventory.
2. **Security scope at baseline:** sensitivity and authorization were initially missing. F3 adds demo-role guards and read filtering, but roles remain simulated and are not production authentication.
3. **Ingestion behavior at baseline:** uploads were metadata-only and parsing defaulted to project-wide reparse. F2 adds file persistence and per-source reparsing.
4. **Extraction behavior:** AI extraction sends stored excerpts to external providers. Validate fallback order, response validation, errors, secret redaction, and whether malformed/empty responses overwrite prior claims.
5. **Verification semantics:** `VERIFIED` currently means two distinct filenames are linked, not that sources independently corroborate the same proposition. Contradictions are not detected by the validator.
6. **Persistence:** SQLite defaults to the project directory and is not durable by itself on ephemeral hosting.
7. **Review workflow at baseline:** reviewer identity was fixed and authorization absent. F3 now looks up the seeded user for the selected demo role, checks permissions, and audits allowed/denied review attempts.
8. **Phase 0 local state:** the database and application/data files were already modified in the worktree. The F1 fix removed the database from Git's index and added `*.db` to `.gitignore`; tests use temporary databases.

## Phase 0 scope boundary

This document began as Phase 0/1 static reconnaissance; implementation and later verification updates are recorded below.

## Local run and demo database commands

Run these commands in PowerShell from the application directory:

```powershell
Set-Location 'D:\STudy\Hackathon\CodersInPune\HandoverTrail'
.\.venv\Scripts\python.exe -m streamlit run app.py
```

To reset the demo database to a fresh seeded demo state, first make a timestamped backup in the system temp directory, then remove and bootstrap the database:

```powershell
Set-Location 'D:\STudy\Hackathon\CodersInPune\HandoverTrail'
$env:HANDOVERTRAIL_DB = Join-Path (Get-Location) 'handovertrail.db'
if (Test-Path $env:HANDOVERTRAIL_DB) {
    $backup = Join-Path $env:TEMP ("handovertrail-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.db')
    Copy-Item $env:HANDOVERTRAIL_DB $backup
    Write-Output "Database backup: $backup"
}
Remove-Item $env:HANDOVERTRAIL_DB -Force -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -c "from database import bootstrap; bootstrap()"
Remove-Item Env:\HANDOVERTRAIL_DB
.\.venv\Scripts\python.exe -m streamlit run app.py
```

This reset is destructive to the current database; keep the printed backup path if existing data may be needed. Bootstrap automatically registers and parses packaged demo sources and seeds cached claims as pending; no API call is needed for the initial claims.

## Phase 1 verification record

- At the Phase 1 baseline, `handovertrail.db` was tracked. F1 removed it from the Git index while retaining the local file; in the current branch `git ls-files --error-unmatch HandoverTrail/handovertrail.db` finds no tracked path and `git check-ignore HandoverTrail/handovertrail.db` confirms it is ignored.
- A shallow fresh clone of `origin/main` at commit `24dc942` started with the existing project virtual environment. Streamlit's `/_stcore/health` endpoint returned HTTP 200 / `ok`. The clone had no ignored local secrets; this was a startup check, not an extraction workflow test.
- `python -m compileall` passed for project Python sources and `python -m pip check` reported no broken requirements.
- `git diff --check` reported existing trailing-whitespace issues in modified app/source files and demo data; no whitespace cleanup was made.
- A heuristic credential scan found no recognized credential patterns in the 23 reachable Git commits or scanned tracked text files. It did find an OpenRouter-key-shaped value in local `.streamlit/secrets.toml`, which is ignored by Git; the value was suppressed and not printed. This scan is pattern-based, not proof that all secrets are absent.
- One real generic request to OpenRouter succeeded: configured route `openrouter/auto`, answering model `deepseek/deepseek-v4.1-flash-1017`. No project evidence was included in this request.
- `pytest` and `ruff` are not installed in the current virtual environment, and no existing automated test suite was found during Phase 0 inventory.

## P0 gap report (approval gate)

| # | Expected gap | Phase 1 result |
|---|---|---|
| 1 | No role-based permission filtering or source sensitivity | **Confirmed.** No source sensitivity field or backend source authorization guard was found; handover reads approved claims and evidence without role filtering. |
| 2 | Custom upload does not persist file contents | **Confirmed.** The page registers uploaded filenames/metadata but does not save the uploaded bytes; the parser reads from a local path. |
| 3 | OpenRouter/heuristic fallback is not labelled in the UI | **Not a current gap.** The Review Claims page displays the result method and fallback reason; the extraction progress messages also identify Gemini, OpenRouter, or the local heuristic. |
| 4 | “Verified” means two filenames; no conflict detection | **Confirmed.** The validator uses distinct filenames as its verification threshold and does not compare claim meaning or detect contradictions. |
| 5 | No authorization on approve/reject | **Confirmed.** Review actions update claims using a hard-coded demo reviewer ID; no server-side role/permission guard is checked before approval or rejection. |

Phase 1 completed before the user approved F1–F9. The sections above preserve the original baseline findings; the approved fixes and final checks are recorded below and in `QA_SESSION_LOG.md`.

## Final implementation and verification

- F1–F7 were implemented and committed separately; F6 was corrected so the cached claims match the user-approved payment-gateway demo fixtures included in the repository.
- A legacy-schema check confirmed bootstrap adds `sources.sensitivity` and `claims.claim_source` and seeds four cached claims.
- `python -m pytest -q tests` passed all 14 backend tests; the recorded output is `qa/results_backend.txt`.
- The final fresh-clone run at commit `36f0691` returned HTTP 200 / `ok`. With an empty disposable database, bootstrap seeded the demo claims; a Reviewer approved a public claim; Incoming saw that claim and three public citations, while one approved restricted-only claim was hidden and counted without exposing its text.
- Incoming role selection remained stable when navigating between Review Claims and Handover View.
- No provider request was made during the final browser journey. Total real calls in the approved phase remained 4 of 5.
- The local database path was ignored and not tracked. No Streamlit Community Cloud deployment was run.
