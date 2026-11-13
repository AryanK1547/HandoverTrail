# HandoverTrail

HandoverTrail turns project notes, chat exports, code summaries, and task lists into an evidence-linked handover.
Reviewers can inspect and approve candidate claims before they are shown to incoming teammates.
The demo includes role and source-sensitivity filtering, a local SQLite database, and optional AI extraction.

  **Live demo:** https://handovertrail-aryankhode.streamlit.app/

## Workflow

1. Load the packaged demo or upload `.txt` and `.csv` sources.
2. Parse sources into excerpts linked to their filenames and chunk locations.
3. Extract candidate claims with Gemini, then the pinned OpenRouter model, or use the labeled local heuristic fallback.
4. Review and approve or reject claims as Admin or Reviewer.
5. Inspect conflicts and evidence gaps, then view approved, authorized claims and citations as Incoming.

An empty database is seeded with demo sources and cached demo claims, so the review flow can be explored without an API call.

## Run locally

From the repository root in PowerShell:

```powershell
Set-Location '.\HandoverTrail'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The app uses `handovertrail.db` beside `database.py` by default. Set `HANDOVERTRAIL_DB` to choose another SQLite file. Uploads are stored under `uploads/<project_id>/`.

To install the test dependency and run the backend suite:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q tests
```

## AI provider configuration

Optional Streamlit secrets are named `GEMINI_API_KEY` and `OPENROUTER_API_KEY`. Do not commit credentials.

Gemini uses `gemini-3.6-flash`. If Gemini is unavailable, the configured OpenRouter fallback is `deepseek/deepseek-v4.1-flash-1017`. If neither provider can be used, the app labels its local heuristic fallback. AI extraction is limited to three runs per browser session.

Only public-sensitivity excerpts can be sent to Gemini or OpenRouter. Before a provider call, common email addresses, phone numbers, credential-like tokens, and long numeric ID patterns are masked. Restricted excerpts stay local and use the heuristic extractor. Incoming display also masks those common patterns. Pattern matching can miss unusual or unknown sensitive formats; do not send real sensitive data, and do not use the demo role selector as a security boundary.

## Roles and evidence labels

- **Admin** and **Reviewer** can read public and restricted demo sources and can review claims.
- **Incoming** can read approved claims only when every linked source is public.
- Roles are simulated by a Streamlit selector; there is no login or authenticated identity.
- **Corroborated** means matching subject/attribute values were found across separate sources after name/date normalization. A different value is shown as a conflict or possible conflict for review.
- **Evidence gaps** include tasks without owners, decisions without dates or rationale, risks without mitigation, and single-source claims. The current detector uses explicit text rules and may miss differently worded statements.
- Conflict comparisons are deterministic and run locally; provider calls are not used for conflict or gap detection.

The demo's restricted source is synthetic test data, not a real credential or contact record.

## Design and usability

The shared interface uses one five-step workflow rail, a role badge, and next-step guidance computed from visible database state. Review and handover cards keep trust, human review, source sensitivity, and extraction origin as separate labels. Text uses a dark-theme palette with contrast-tested tokens; focus outlines are visible, and the 375 px workflow rail collapses to a compact current-step label. The role selector remains a demo control, not authentication.

## Streamlit Community Cloud

Deployed on Streamlit Community Cloud and manually checked by the author on 11 Nov 2026. Hosted storage is not durable, so data resets when the app restarts. For a trial deployment, connect the repository, select `HandoverTrail/app.py`, ensure `HandoverTrail/requirements.txt` is installed, and configure the optional secret names above in the Cloud settings.

The app writes SQLite data and uploaded files to local storage. Streamlit-hosted local files are not a durable persistence service, so edits or uploads may be lost when an instance is replaced. Use durable external storage and real authentication before production use.
