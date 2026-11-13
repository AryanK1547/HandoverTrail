# HandoverTrail

HandoverTrail turns project notes, chat exports, code summaries, and task lists into an evidence-linked handover.
Reviewers can inspect and approve candidate claims before they are shown to incoming teammates.
The demo includes role and source-sensitivity filtering, a local SQLite database, and optional AI extraction.

  **Live demo:** https://handovertrail-aryankhode.streamlit.app/

**Deployment QA (13 Nov 2026):** The public app was available on merged `main`
(`839953b`). No user-initiated approval, upload, resolution, or release was
performed, but opening Review Claims automatically recalculates and persists
derived conflict/gap records. This was not a complete live acceptance test.
The Incoming handover is empty until a reviewer releases a snapshot, and the
Upload Sources page currently exposes upload and parsing controls to Incoming.
These are findings about the deployed commit, not the current local worktree:
the workspace-isolation and UX fixes described below are on `r3/ux-hardening`
and have not been pushed or deployed. Use synthetic data only; simulated roles
and URL workspaces are not authentication or a security boundary.

## Workflow

1. Load the packaged demo or start an isolated upload workspace and add `.txt`,
   `.md`, or `.csv` sources. Upload workspaces do not include cached demo claims.
2. Parse sources into excerpts linked to their filenames and chunk locations.
3. Extract candidate claims from the selected workspace and sources with Gemini,
   then the pinned OpenRouter model, or use the labeled local rule-based fallback.
   The fallback keeps explicit source statements rather than summarizing them.
   The latest result and method remain visible after refresh.
4. Search, filter, and page through claims. Check evidence, then review, edit,
   and approve them; an edit returns the claim to pending review and is retained
   in History.
5. Inspect conflicts and evidence gaps, then create questions from open gaps; the assigned Departing role answers them as interview evidence.
6. Release a handover snapshot as Admin or Reviewer; Incoming sees that latest release and can acknowledge its version.

An empty database is seeded with demo sources and cached demo claims, so the
demo review flow works without an API call. Each uploaded workspace has its own
project, sources, claims, and extraction history; it does not reuse the demo
claims. A random workspace token in the URL restores that workspace after navigation
or refresh. In-app navigation also restores the active workspace for the
current Streamlit session if a page link drops the token. Anyone who has the
link can access it, so do not put sensitive or private project data in this demo.

## Run locally

From the repository root in PowerShell:

```powershell
Set-Location '.\HandoverTrail'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The app uses `handovertrail.db` beside `database.py` by default. Set `HANDOVERTRAIL_DB` to choose another SQLite file. Uploads are stored under `uploads/<project_id>/`.
For test or alternate upload storage, `HANDOVERTRAIL_UPLOADS_DIR` overrides the
uploads root. These local directories are not durable hosted storage.

To install the test dependency and run the backend suite:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q tests
```

For browser-based user journeys, install Node.js and npm, then run from
`HandoverTrail`:

```powershell
npm ci
npx playwright install chromium
npm run test:e2e
```

Playwright is a browser automation tool: these tests click through the app and
check what a user sees. The runner starts Streamlit on an available local port,
uses temporary SQLite and upload directories, disables Gemini/OpenRouter calls,
and removes the temporary data afterward. No API keys are needed for tests.

## AI provider configuration

Optional Streamlit secrets are named `GEMINI_API_KEY` and `OPENROUTER_API_KEY`. Do not commit credentials.

Gemini uses `gemini-3.6-flash`. If Gemini is unavailable, the configured OpenRouter fallback is `deepseek/deepseek-v4.1-flash-1017`. If neither provider can be used, the app labels its local rule-based fallback;
it only recognizes explicit wording and may miss indirectly phrased claims.
AI extraction is limited to three runs per browser session.

Only public-sensitivity excerpts can be sent to Gemini or OpenRouter. New uploads
default to Restricted and therefore use local rule-based extraction unless the
reviewer changes the sensitivity to Public. Before a provider call, common email
addresses, phone numbers, credential-like tokens, and long numeric ID patterns
are masked. Incoming display also masks those common patterns. Pattern matching
can miss unusual or unknown sensitive formats; do not send real sensitive data,
and do not use the demo role selector as a security boundary.

Provider extraction is limited to 80,000 evidence characters per run. Larger
selected input is not sent to a provider; the app reports the reason and uses
the local rule-based fallback. Repeated extraction of the same claim/evidence does not
replace reviewed claims or create duplicate candidates.

## Roles and evidence labels

- **Admin** and **Reviewer** can read public and restricted demo sources and can review claims.
- **Incoming** can read approved claims only when every linked source is public.
- Incoming cannot upload sources or review candidate claims in the local UX
  fixes; it sees only the latest released snapshot on Handover View.
- **Departing** can read and answer only questions assigned to the demo leaver. Public interview evidence stays hidden from Incoming until all claims linked to that answer are approved.
- **Handover release:** Incoming sees a fixed release snapshot, not live claims. A later edit requires approval and a new release; acknowledgement is recorded against the exact released version.
- Roles are simulated by a Streamlit selector; there is no login or authenticated identity.
- Deployed gap (commit `839953b`): Incoming could see upload and parse controls. That deployed code is not yet updated with the local role-gating fix.
- **Corroborated** means matching subject/attribute values were found across separate sources after name/date normalization. A different value is shown as a conflict or possible conflict for review.
- **Evidence gaps** include tasks without owners, decisions without dates or rationale, risks without mitigation, and single-source claims. The current detector uses explicit text rules and may miss differently worded statements.
- Conflict comparisons are deterministic and run locally; provider calls are not used for conflict or gap detection.
- Exit-interview questions use local templates. Answers are saved with the demo author and timestamp as an `interview` source, chunked, and extracted only from that source into pending claims. The current interview extractor uses local rules and does not make provider calls.

The demo's restricted source is synthetic test data, not a real credential or contact record.

## Design and usability

The shared interface uses one six-step workflow rail, a role badge, and
next-step guidance computed from visible database state. Review provides
search, status/evidence/validation filters, pagination, persistent extraction
status, and evidence-check badges so large claim queues can be narrowed.
Incoming gets release-specific context and acknowledgement state, not the
candidate review queue. Review and handover cards keep trust, human review,
source sensitivity, and extraction origin as separate labels. Text uses a
dark-theme palette with contrast-tested tokens; focus outlines are visible,
and the 375 px workflow rail collapses to a compact current-step label.

## Streamlit Community Cloud

Deployed on Streamlit Community Cloud. The public URL returned the app on
13 Nov 2026 and its footer reported commit `839953b`. The earlier author check
was on 11 Nov 2026; the 13 Nov QA check made no user-initiated write actions,
but opening Review Claims automatically refreshed derived conflict/gap
records. The check did not verify live provider extraction, upload handling,
release/acknowledgement, or restart behavior. Cloud Python version and secret
values are not visible in the app.
Streamlit documents that apps without traffic for 12 hours sleep; a visitor
sees a wake-up screen and can request that the app start again. That screen and
the wake time were not observed in this QA run. Hosted storage is not durable,
so local SQLite data and uploads may reset when the app restarts or its
instance is replaced.

The live app currently runs the merged `main` code noted above; this worktree's
workspace and UX fixes have not been pushed. The app writes SQLite data and
uploaded files to local storage. Streamlit-hosted
local files are not a durable persistence service. The initial reviewer queue
contains pending claims and there is no released handover in the observed live
state, so Incoming sees an empty handover until a Reviewer or Admin releases
one. Use durable external storage and real authentication before production use.
