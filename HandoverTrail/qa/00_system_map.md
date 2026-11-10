# HandoverTrail System Map

Phase 0 reconnaissance, 2026-11-10.

## Runtime and entry points

- The application is a Python/Streamlit multipage app. `app.py` is empty; Streamlit discovers the scripts under `pages/`.
- The current runtime stack declared in `requirements.txt` is Streamlit, pandas, and `google-genai`.
- The database is SQLite at the relative path `handovertrail.db`. The connection helper enables SQLite foreign-key enforcement.
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
  ├─ OpenRouter if Gemini fails
  └─ local keyword heuristic if both AI providers fail
         │
         ▼
`claims` + `claim_evidence`
         │
         ├─ Validate button → `validator.py` updates trust status
         ├─ Reviewer actions → update claims and insert review records
         └─ Handover page → displays approved claims and linked evidence
```

## Component responsibilities and observed boundaries

| Component | Observed responsibility |
|---|---|
| `app.py` | Empty; no explicit app-level router or session initialization. |
| `database.py` | Creates eight SQLite tables: users, projects, sources, evidence_chunks, claims, claim_evidence, reviews, and audit_logs. Enables foreign keys per connection. |
| `source_parser.py` | Parses CSV rows and groups non-empty TXT lines in windows of three, then stores evidence chunks. Resolves files from the demo directory or the current working path. |
| `extractor.py` | Builds an evidence prompt, validates returned claim types and evidence IDs, calls Gemini then OpenRouter, and falls back to keyword grouping. Saves generated claims and their evidence links. |
| `validator.py` | Sets `MISSING_EVIDENCE` when no linked evidence exists, `VERIFIED` when linked chunks come from two or more distinct filenames, otherwise `SINGLE_SOURCE`. |
| `permissions.py` | Empty in the inspected worktree. No permission guard is implemented here. |
| `retrieval.py` | Empty in the inspected worktree. |
| `models.py` | Empty in the inspected worktree. |
| `pages/1_Upload_Sources.py` | Creates the demo project, registers demo/custom source metadata, calls the parser, and displays chunks. |
| `pages/2_Review_Claims.py` | Calls extraction and validation; displays evidence; includes a hard-coded demo reviewer and approve/reject actions. |
| `pages/3_Handover_View.py` | Queries approved claims for the demo project and renders their linked evidence. |

## Schema and QA fixture compatibility

- The source schema has no sensitivity/classification field. The `sources` table stores source ID, project ID, filename, file type, and upload time.
- The provided QA fixture includes `sensitivity` labels to describe intended security cases; those fields are not currently represented in the application schema or ingestion path.
- The database has claim trust states including `CONFLICTING`, but the current validator does not detect contradictory claims; it only counts supporting filenames.
- The current handover page filters for `review_status = 'APPROVED'`, but there is no role-based authorization check or restricted-source filtering in that page.
- Custom uploads register metadata, but the inspected upload page does not persist uploaded file bytes. The parser later resolves the filename from the local demo directory or working directory.

## Phase 0 observations and risks for later QA

1. **High priority, verify in Phase 1/2:** no automated `tests/` or `qa/` suite was present at initial inventory.
2. **Security scope:** the brief's sensitivity and immutable authorization guard are not implemented in the inspected code; do not treat session/UI state as authorization.
3. **Ingestion behavior:** verify custom-upload persistence, missing files, duplicate names, and repeated parsing. Parsing defaults to `force_reparse=True` and deletes existing evidence chunks for the project before rereading files.
4. **Extraction behavior:** AI extraction sends stored excerpts to external providers. Validate fallback order, response validation, errors, secret redaction, and whether malformed/empty responses overwrite prior claims.
5. **Verification semantics:** `VERIFIED` currently means two distinct filenames are linked, not that sources independently corroborate the same proposition. Contradictions are not detected by the validator.
6. **Persistence:** the SQLite location is relative to the process working directory and is not durable by itself on ephemeral hosting.
7. **Review workflow:** reviewer identity is fixed in the page code; authorization is not enforced by the review action.
8. **Current local state:** `handovertrail.db` and multiple application/data files are already modified in the worktree. Later QA should isolate tests with temporary databases and avoid changing the active DB.

## Phase 0 scope boundary

This document records static reconnaissance only. Static checks, dependency auditing, automated test authoring/runs, browser testing, and fixes are deferred to later phases.

## Local run and demo database commands

Run these commands in PowerShell from the application directory:

```powershell
Set-Location 'D:\STudy\Hackathon\CodersInPune\HandoverTrail'
.\.venv\Scripts\streamlit.exe run app.py
```

To reset the demo database to an empty schema, first make a timestamped backup in the system temp directory, then remove and recreate the database:

```powershell
Set-Location 'D:\STudy\Hackathon\CodersInPune\HandoverTrail'
if (Test-Path .\handovertrail.db) {
    $backup = Join-Path $env:TEMP ("handovertrail-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.db')
    Copy-Item .\handovertrail.db $backup
    Write-Output "Database backup: $backup"
}
Remove-Item .\handovertrail.db -Force -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -c "from database import init_db; init_db()"
.\.venv\Scripts\streamlit.exe run app.py
```

This reset is destructive to the current database; keep the printed backup path if existing data may be needed. After reset, open **Upload Sources**, load the packaged demo files, and process/chunk them to repopulate the demo workflow.

## Phase 1 verification record

- `handovertrail.db` **is tracked in Git** (`git ls-files --error-unmatch handovertrail.db` succeeded). The current working copy contains local modifications; do not use `git restore` as a reset shortcut.
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

Phase 1 is complete. Phases 2–5 and all application-code changes are intentionally stopped pending user approval.
