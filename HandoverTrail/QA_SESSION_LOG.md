# QA Session Log

## Session log

- Date/time: 2026-11-10 12:41 IST
- Phases completed: Phase 0 (Reconnaissance & System Mapping), Phase 1 (Static checks, secret scan, fresh-clone startup, provider check)
- Commands/checks run:
  - Repository/worktree and component inspection; `git ls-files`/`git check-ignore` for database and secrets tracking.
  - `python -m compileall` on project Python sources: passed.
  - `python -m pip check`: passed, no broken requirements.
  - `git diff --check`: reported trailing whitespace in modified files and demo data; no cleanup performed.
  - Heuristic credential scan of tracked text, local ignored secrets, and all 23 reachable commits. No recognized patterns in tracked files/history; an OpenRouter-key-shaped value was found in ignored local `.streamlit/secrets.toml`. Its value was never printed.
  - Fresh shallow clone of `origin/main` at `24dc942`, launched with the existing virtual environment; Streamlit health endpoint returned `ok`.
  - One real generic OpenRouter request: `openrouter/auto` succeeded and reported answering model `deepseek/deepseek-v4.1-flash-1017`. No project evidence was sent.
- Files created/updated: `qa/00_system_map.md` (run/reset commands, DB tracking state, Phase 1 results, P0 report), `QA_SESSION_LOG.md`; Phase 0 fixture remains `qa/fixtures/sample_project.json`.
- Findings: Confirmed gaps are absent source sensitivity/role filtering; custom upload bytes are not persisted; verification is based on two filenames and does not detect contradiction; approve/reject has no server-side authorization. Expected gap 3 is not present in the current worktree: provider/fallback method and reason are shown in the UI.
- Real LLM calls used: 1 / 10 (generic OpenRouter health request; no evidence or project content).
- Blocked/limitations: `pytest` and `ruff` are not installed; no test suite was found in initial inventory. The credential scan is heuristic and cannot guarantee that no secrets exist. Fresh clone verified startup/health only, not the full upload-to-handover flow.
- During Phase 1, application code changed: No.
- Approval gate: Phases 2–5 are not started. Await user approval before implementing any P0 remediation.
- F1 completed after approval: Added project-root SQLite path with `HANDOVERTRAIL_DB` override; added idempotent bootstrap/schema migration and demo role/project seeds; added the landing page, demo-load action, and a session-persisted role selector on every page; removed the database from Git's index while retaining the local file; ignored `*.db` and `uploads/`.
- F1 concepts/tools in plain words: `pathlib` builds filesystem paths safely instead of hand-joining strings; `HANDOVERTRAIL_DB` is an environment setting that lets tests/deployments choose a database without editing code; SQLite `PRAGMA table_info` asks the DB which columns exist and `ALTER TABLE` adds a missing column without recreating existing data; Streamlit session state remembers the selected demo role while that browser session is active, but is not real authentication; `git rm --cached` stops tracking a file in Git while leaving the local copy intact.
- F1 verification: fresh temporary DB bootstrapped twice with exactly three demo roles and one demo project; `sensitivity` migration passed; Python compilation passed; app health returned `ok` using a fresh temporary DB. Existing DB backup is at `%TEMP%\handovertrail-pre-qa-fixes-20261110-124921.db`.
