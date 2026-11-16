# Testing

## Backend suite

Run from the application directory:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests
```

Round 2 baseline: **15 passed**. R3-0 added an additive migration test; the R3-0 result was **16 passed**. R3-1 passed **23 tests**; the R3-UI suite passed **25 tests**. R3-2 passed **30 tests**; R3-3 passed **32 tests**; R3-4 passed **34 tests**; R3-5 passes **36 tests**. Tests use temporary databases selected through `HANDOVERTRAIL_DB`; they cover sensitivity-aware retrieval and role checks, upload validation/parsing, cached demo evidence anchors, badge HTML escaping, UI contrast-token thresholds, conflict/gap rules, exit-interview lifecycle, claim history, immutable releases, acknowledgements, and audited actions.

R3-1 coverage adds synthetic-only checks for email, phone, credential-like token, and ID-number masking; both provider gateway paths are replaced with fake functions in tests; restricted chunks are rejected at the gateway; mixed-sensitivity extraction sends only public chunks to a fake provider and handles restricted chunks locally; provider failure falls back locally; and Incoming retrieval masks claim text and public evidence. OpenRouter request construction is tested using a fake HTTP transport. These tests do not make real provider requests.

Streamlit `AppTest` also rendered the landing page and all source/review/handover scripts against a fresh temporary database without app exceptions. Its first default-timeout attempt expired; rerunning each script with a 20-second test timeout passed. This is a local startup/UI smoke check, not a live Cloud test.

R3-2 uses deterministic local comparisons: owner/name case and punctuation are normalized, common full and partial dates are normalized, and similar subject text with differing values is marked **Possible conflict** instead of a definite conflict. Tests cover disagreeing owners, agreeing normalized names/dates, missing task owners, missing decision dates/rationale, missing risk mitigation, single-source claims, and a resolution audit row. No LLM or network requests are used by these tests.

An isolated AppTest bootstrapped a fresh database and rendered the Review Claims page with all three synthetic disagreements, their citations, and resolution buttons. The first R3-2 full-suite run exposed two old cold-start count assertions; the packaged demo now intentionally includes eight sources, 17 evidence chunks, and 13 cached pending claims, and the assertions were updated. The final full suite and checks are recorded in `QA_SESSION_LOG.md`.

R3-3 tests cover template generation for every gap type, idempotent regeneration, reviewer add/edit/delete/send actions, per-user question isolation, public interview-source withholding until approval, answer authorship/timestamp/sensitivity, source chunking, scoped extraction that preserves old claims, pending review status, and resolution after approval. Interview extraction is forced through the local heuristic in tests; the provider functions are replaced with fail-fast fakes, so tests cannot make real provider calls. AppTest rendered the page for both Reviewer and Departing roles with no exceptions.

R3-4 tests verify that edits append the replaced text with its reason/editor/time, version numbers remain ordered across edits, the edit and audit records are saved, and an approved claim becomes edited-pending-review and disappears from Incoming until reapproved. The Review Claims AppTest rendered history/edit forms for all seeded claims and conflict controls without exceptions.

R3-5 tests verify that releases include only approved claims with evidence exclusively from public sources, mask common contact values in the snapshot, remain unchanged after source/claim edits, and reject direct snapshot update/delete attempts. Role tests reject release by Incoming and acknowledgement by reviewers; Incoming can acknowledge the latest version once, and a later release increments the version and requires a separate acknowledgement.

The UI snapshot set is in `qa/ui/`: `before-375.png`, `before-768.png`, `before-1440.png`, and matching `after-*.png` files. At all three viewport widths the document and body widths matched the viewport width. At 375 px the saved screenshot has the Streamlit sidebar open because the browser viewport was resized from desktop; the navigation drawer must be collapsed to see the page content. The mobile rail collapsed to a single step label.

## Startup and fresh-clone journey

- A fresh clone of the `qa-fixes` branch started with an empty disposable database. The health endpoint returned HTTP 200 / `ok`.
- Bootstrap loaded the packaged sources and cached pending claims before an API request. After R3-2, a fresh database contains eight sources, 17 evidence excerpts, and 13 cached pending claims. The landing-page “Load demo project” action confirmed the demo was ready.
- A Reviewer approved one cached public claim. A second synthetic restricted-only claim was approved through the Reviewer permission function in the disposable database.
- After switching to Incoming and navigating from Review Claims to Handover View, the role remained Incoming. The review queue showed only the approved public claim; the handover showed its three public citations and reported one hidden restricted claim without displaying its text.
- A migration check starting from the older `sources` and `claims` schemas confirmed bootstrap added `sensitivity` and `claim_source`; the additive Round 3 schema and synthetic fixture seeding are also covered by pytest.

## Provider checks

Gemini model listing and pinned Gemini/OpenRouter requests were completed earlier in the approved phase. No provider request was made in the final fresh-clone journey or after the 4-of-5 call budget was reached.

## Deployed Phase D (no user-initiated writes)

Run on 13 Nov 2026 against
`https://handovertrail-aryankhode.streamlit.app/`. The public app footer showed
`839953b`, matching `origin/main` at
`839953ba1c7a79f3d31e99601fe5db7ebeb6c5b5`. A clean browser load reached the
landing page in about 12 seconds. Direct URLs for Review Claims, Handover View,
and Exit Interview rendered; Upload Sources returned HTTP 200 and rendered
through in-app navigation. The initial reviewer state displayed 8 sources,
17 excerpts, 13 pending claims, and 22 open gaps. Incoming was shown 7 sources
and 15 excerpts, with zero approved claims and zero released versions.

Streamlit's current Community Cloud documentation says apps without traffic
for 12 hours go to sleep and visitors see a sleeping page with a “Yes, get this
app back up!” action. The live app was not left idle for 12 hours, so its
actual sleep screen and wake time were not tested. Source:
<https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app#app-hibernation>.

Browser checks at 375, 768, and 1440 CSS pixels found the Upload
Sources document width equal to the viewport width at each size. The Reviewer
view showed three Version A/Version B comparisons, 13 pending claim cards,
history expanders, and evidence references. The Exit Interview page exposed
the Reviewer question-preparation controls; the Departing view correctly
showed no project claims/sources and an empty assigned-question state.

Opening Review Claims as Admin/Reviewer automatically invokes conflict
detection. That code rebuilds derived claim slots and inserts or refreshes
conflict/gap records. This shared-database side effect was not apparent before
the page was opened; exact before/after row counts were not collected. No
user-initiated review, upload, resolution, interview, release, or acknowledgement
action was performed.

**Important live finding:** Incoming could see the Upload files tab, file
picker, sensitivity selector, “Save and process uploaded files” button,
“Load pre-packaged demo files” button, and “Parse unprocessed sources” button.
No upload, demo-load, parse, approval, rejection, conflict resolution, release,
acknowledgement, reboot, or real provider request was performed. The live
Review Claims and Upload Sources rendered page markup did not contain the
synthetic restricted markers checked in this run. The review controls for
approval were not available to Incoming; extraction and validation were
disabled and there were no visible claims to review.

Changing the role in the selector affected that browser session and
cross-page navigation. A full browser refresh reset the role to Admin.
Adding `?role=reviewer` did not set the Reviewer role; a new app session used
its default Admin role. These are demo behaviors, not authentication.

The Incoming Handover View displayed “No handover has been released yet.”
and “A Reviewer or Admin must release an approved snapshot before it appears
here.” The reviewer queue was entirely pending. This is a material first-visit
judge risk because no release/acknowledgement journey can be completed without
state-changing actions.

The page reported “2 MB per file” while the upload widget reported “200MB per
file.” Upload validation/rejection cases were not exercised. One unidentified
404 resource was logged on page loads; a third-party Heap analytics request
was aborted, and the browser emitted Streamlit feature-policy/sandbox warnings.
No application stack trace was observed. Screenshots were not exported to
workspace files; see `DEPLOYED_QA_REPORT.md` for evidence limits and the owner
checklist.

### Not tested on the live service

- Approving/rejecting claims, conflict resolution, interview question
  generation/answer submission, claim editing, release, or acknowledgement:
  these write to the single shared database.
- Gemini/OpenRouter extraction: no real provider call was made, so the
  configured model names and actual provider response are not verified here.
- Empty-database Cloud bootstrap, app reboot/ephemeral-storage behavior,
  concurrent uploads, file-input edge cases, XSS/prompt injection, keyboard
  behavior, Firefox/WebKit, browser back/forward, or two-session concurrency.
- Streamlit Cloud Python version, logs, configured secret names, and provider
  dashboard quotas; these require the owner’s Cloud/API access.

The complete coverage matrix, priorities, and re-run instructions are in
[`DEPLOYED_QA_REPORT.md`](./DEPLOYED_QA_REPORT.md). The checks made no
user-initiated writes, but Review Claims rendering automatically refreshed
derived conflict/gap records. This is not proof that all three improvements
work end-to-end in production.

## Local workspace and UX regression tests

On `r3/ux-hardening`, the focused backend suite contains **40 tests**. It uses
temporary SQLite files and synthetic inputs; provider functions are replaced
or disabled so the tests do not call Gemini or OpenRouter.

The browser suite uses Playwright, a tool that opens Chromium and operates the
app like a user. From the `HandoverTrail` directory:

```powershell
npm ci
npx playwright install chromium
npm run test:e2e
```

The runner selects a free local port, starts Streamlit with a temporary
database and uploads directory, disables provider calls, and removes its
temporary data afterward. Docker is not required because the app's local test
database is SQLite.

The three browser journeys cover:

- Reviewer validation, claim search, and return after a browser refresh.
- Reviewer approval and release, followed by Incoming viewing and
  acknowledging the released version.
- Markdown upload and extraction in a new workspace, no demo-claim mixing, refresh
  persistence, then a second empty workspace that remains isolated from the
  first.

The Playwright result is local browser evidence only; it does not verify the
public Cloud deployment, real provider responses, multiple browsers, or
authenticated access. The workspace token is an access-by-link demo mechanism,
not a login.
