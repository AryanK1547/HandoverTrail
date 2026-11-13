# Deployed QA Report — Phase D

**Checked:** 13 Nov 2026, approximately 16:47–16:55 IST  
**Target:** https://handovertrail-aryankhode.streamlit.app/  
**Browser:** Integrated Playwright-controlled Chromium; new app tab, separate incognito context not exposed  
**Scope:** No user-initiated write actions; synthetic data; no real provider requests  
**Working branch:** `r3/qa`, based on `origin/main`; no push

Local validation on this branch: Python 3.11.9; `.\.venv\Scripts\python.exe -m pytest -q tests` → **36 passed in 4.70 seconds**. `git diff --check` passed.

## Verdict

**NO-GO for claiming a fully verified Round 3 submission based on this evidence.** The app is
available and the new UI is present, but the end-to-end live workflows were
not run because they would mutate one shared database or spend provider quota.
The Incoming handover was empty, Incoming had write controls on Upload Sources,
and a schedule check found Round 3 commits before the opening time specified in
the plan. The last item could affect eligibility and cannot be corrected by
rewriting history.

**Single biggest risk:** `ROUND3_MASTER_PLAN.md` says the Round 3 window opened
at 23:59 IST on 13 Nov 2026. `origin/main` shows Round 3 implementation and
merge commits from 01:43 through 16:23 IST that date. If judges enforce the
published opening time, the Round 3 work may be ineligible. Preserve history
and ask the organizer how to proceed. This Phase D check itself ran at about
16:47–16:55 IST on 13 Nov, also before the stated opening time and before the
plan's Monday QA block; confirm whether this evidence is eligible too.

## D0 — Baseline

- GitHub repository: public.
- Deployed branch: `main`; live footer showed short SHA `839953b`.
- `origin/main`: `839953ba1c7a79f3d31e99601fe5db7ebeb6c5b5`
  (`Merge pull request #9 from AryanK1547/r3/handover-release`).
- Main app file: `HandoverTrail/app.py`.
- Sidebar pages observed: `app`, `Upload Sources`, `Review Claims`,
  `Handover View`, and `Exit Interview`.
- README links to the live URL. `ROUND3_PLAN.md`, the requested technical
  documentation, and the root MIT `LICENSE` are present on `main`.
- Runtime Python version and Cloud-installed package versions were not
  visible from the app.

## D1 — Availability and cold start

- **D1.1 PASS (availability only):** A new browser tab first showed Loading;
  the landing screen became meaningful about 12 seconds later. The app was
  available during the check.
- **D1.2 PARTIAL:** Streamlit's current Community Cloud documentation says
  apps without traffic for 12 hours go to sleep; a visitor sees the sleeping
  page and may click “Yes, get this app back up!” The live app was not left
  idle for 12 hours, so the actual screen and wake time were not tested. A
  roughly 12-second first render is not enough to distinguish network delay,
  app startup, or wake-up. Source:
  <https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app#app-hibernation>.
- **D1.3 NOT TESTED on Cloud:** The Cloud database was not emptied. The
  observed reviewer state had 8 sources, 17 excerpts, 13 pending claims, and
  22 open gaps. Local tests cover empty temporary databases; they do not prove
  a live Cloud cold-start.
- **D1.4 PARTIAL:** Direct URL navigation rendered Review Claims, Handover
  View, and Exit Interview. Upload Sources returned HTTP 200 and rendered
  through the app's navigation; a separate typed-URL browser run was not
  recorded.

## D2 — Judge journey / viewports

- Landing title and one-sentence product description were immediately
  visible, with a Load demo project action and a two-minute workflow guide.
- The current demo was already loaded; reviewer content showed cached claims
  and evidence without needing an API call.
- Reviewer view showed three conflict pairs, 13 candidate claim cards,
  history expanders, and evidence references. No claim was approved or
  rejected.
- After selecting Incoming, Review Claims showed zero claims and disabled
  extraction/validation controls. Handover View said no release existed and
  explained that a Reviewer or Admin must release one. No citations or
  acknowledgement were available.
- At 375, 768, and 1440 CSS pixels, the Upload Sources document `scrollWidth`
  matched its client width. This is a narrow horizontal-overflow check, not a
  full accessibility or visual review.
- Screenshots were **not saved** to `qa/live/`; the browser tool provided
  rendered/accessibility snapshots but no workspace screenshot paths.

## Phase D coverage matrix

| Area | Result | Observation / boundary |
|---|---|---|
| D0 baseline | PASS | Public repo, `main`, SHA, pages, README URL, MIT license confirmed. |
| D1.1 availability | PASS | Meaningful first render in about 12 seconds. |
| D1.2 sleeping/waking | PARTIAL | Official rule checked (12 hours without traffic); live sleep/wake screen not triggered. |
| D1.3 empty Cloud DB | NOT TESTED | Shared deployed DB was not emptied. |
| D1.4 direct pages | PARTIAL | Review, Handover, Exit were loaded by direct URL; Upload was opened through in-app navigation. |
| D2 judge journey | PARTIAL / FAIL | Product explains itself; no released handover; no reviewer decision was made. |
| D3 shared state/concurrency | NOT TESTED | No approval or upload was made; no second independent session was exercised. |
| D3.4 refresh | PARTIAL | Full page refresh reset the selected role to Admin. Database persistence was not tested. |
| D3.5 back/forward | NOT TESTED | No browser history exercise. |
| D4 reboot/persistence | NOT TESTED | Reboot is owner-only and may erase the shared demo state. |
| D5 live AI extraction | NOT TESTED | No Gemini/OpenRouter call; interface label is not proof of provider success. |
| D6.1 Incoming access | FAIL | No claim-review controls were visible, but Upload Sources exposed write controls. |
| D6.2 restricted markers | PASS for rendered UI | Checked markers were absent from Incoming Review/Upload visible text and rendered page markup. |
| D6.3 role query tampering | PASS, limited | `?role=reviewer` did not set Reviewer; a new session used default Admin. |
| D6.4 restricted-only approved claim | NOT TESTED | No approved claims existed in the observed live state. |
| D6.5 Incoming upload | NOT EXECUTED; UI gap confirmed | File picker, sensitivity control, save button, demo load, and parse controls were visible to Incoming. |
| D6.6 review action denial | PARTIAL | No approve/reject action was available in Incoming Review; no denied action/audit row was created. |
| D7 input/injection | NOT TESTED | No uploads or injection payloads were submitted. |
| D8 UX/accessibility | PARTIAL | Titles, role labels, workflow, and page states observed; no keyboard, screen-reader, contrast, or dark-mode live test. |
| D9 performance | PARTIAL | First render estimate recorded; page-switch/extraction latency not benchmarked. |
| D10 browsers | PARTIAL | Chromium only; Firefox and WebKit not tested. |
| D11 repository | PARTIAL | Public, docs, license, pins, and history checked; Cloud settings/logs not accessible. |

### High-priority findings

1. **P0 — Incoming can reach shared write controls.** As Incoming, the Upload
   Sources page displayed the Upload files tab, file picker, source-sensitivity
   selector, Save and process button, Load pre-packaged demo files button, and
   Parse unprocessed sources button. No file was uploaded and no action was
   clicked. This is inconsistent with the read-only Incoming role expectation
   and can affect all visitors.
2. **P0 — Round 3 timestamps precede the stated window.** The Round 3 plan
   opens at 23:59 IST 13 Nov. Main’s R3-0 commit is at 01:43 IST; the R3-5
   implementation commit is at 15:19 IST; the last merge is at 16:23 IST.
   Do not rewrite history; ask the organizer about eligibility.
3. **P1 — First Incoming handover is empty.** There were 13 pending claims,
   zero approved claims, and no release. An Incoming judge cannot see the
   improvements’ final handover or acknowledge a version.
4. **P1 — Role resets after full refresh.** Changing role in the selector
   affected page navigation, but a full refresh returned to Admin. The demo
   has no authenticated identity, so this is not authorization.
5. **P1 — Upload size text conflicts.** The page says 2 MB per file while the
   uploader widget says 200 MB per file. Rejection behavior was not tested.
6. **P2 — Browser console/network noise.** A 404 resource appeared on page
   loads; its source was not identified. A third-party Heap request was
   aborted. Streamlit feature-policy and iframe-sandbox warnings also
   appeared; no app traceback was observed.

## D11 — Repository and submission checks

- `README.md` contains the live URL, run instructions, roles, and limitations.
- `ARCHITECTURE.md`, `CHANGES_FROM_PLAN.md`, `DISCLOSURES.md`,
  `KNOWN_LIMITATIONS.md`, `TESTING.md`, and `ROUND3_PLAN.md` are present on
  `main`; `ROUND3_DELIVERED.md` and this report are newly prepared locally.
- `requirements.txt` pins Streamlit `1.67.0`, pandas `3.1.1`, and
  `google-genai` `3.1.0`. Cloud-installed versions were not visible.
- The repo has an MIT license.
- A high-confidence credential-pattern scan of reachable `main` history
  printed no values and found matches only in `HandoverTrail/tests/test_backend.py`,
  in the provider-masking test area. These are treated as synthetic
  test-fixture matches, not as evidence of a complete secrets audit. No
  credentials were printed.
- Earliest reachable commit: `6f92218` on 10 Nov 2026 02:02 IST, containing
  the initial MVP. It is after the QA brief’s 8 Nov Round 2 cutoff.
- Round 3 history is different: implementation commits occurred on 13 Nov
  before the 23:59 IST Round 3 window start recorded in the master plan.
  This Phase D run also occurred before that start. History was not rewritten.
- `DISCLOSURES.md` lists Gemini, GitHub Copilot, Claude, and the configured
  Gemini/OpenRouter model identifiers. The live provider/model was not
  verified by this run.

## STATE CHANGES MADE

- **Derived database state:** Opening Review Claims as Admin/Reviewer
  automatically called `detect_project_conflicts`. The implementation deletes
  and rebuilds the project's derived `claim_slots`, inserts/refreshes
  `claim_conflicts` and `gaps`, and may mark no-longer-detected conflicts
  stale. This is an automatic page-render side effect. Exact before/after row
  counts were not measured, so the precise delta is unknown.
- **Uploads, approvals/rejections, conflict resolutions, interviews,
  releases/acknowledgements, reboot:** none.
- **Provider calls:** none.
- **Browser-only changes:** role selection, page navigation, viewport resizing,
  and a refresh in the QA browser session.

## Fix-first list

### Under 15 minutes

1. Before inviting judges, have the owner decide whether to pause public
   access. At minimum, warn users not to upload real/sensitive data until
   Incoming write controls are fixed.
2. Change the uploader’s “200MB per file” label or the page’s “2 MB” caption
   so they state one verified limit. Do not claim the validation limit until
   upload tests verify it.
3. Tell judges that the first Incoming Handover is intentionally empty until a
   Reviewer/Admin has approved claims and released a snapshot.
4. Ask the organizer whether pre-opening Round 3 commit times affect
   eligibility; preserve all Git history.

### Under 1 hour

1. Hide or disable source upload, sensitivity changes, demo registration, and
   parsing for Incoming/Departing, and enforce the intended policy at the
   write boundary rather than relying only on UI visibility. Add role tests.
2. Add a deterministic, idempotent demo seed with a small approved public
   subset and a documented release, while retaining pending claims for review
   demonstration. Test first-time Incoming behavior in a temporary database.
3. Decide and document whether role selection should survive refresh; never
   imply that persistence makes the simulated roles secure.
4. Add UI tests for the upload role gate and the first Incoming release state.

### Round 3 / before calling the workflow complete

1. Re-run a complete, owner-approved live journey on an isolated or resettable
   deployment: approve, reject, resolve, create/send/answer an interview,
   review its pending claim, edit/history, release, and acknowledge.
2. Verify Cloud restart/ephemeral behavior and inspect logs/settings with the
   owner; do not expose secret values in evidence.
3. Test provider behavior only with owner approval and within the remaining
   quota; report the actual provider, model, time, and fallback messages.
4. Add per-visitor isolation, real authentication, and durable storage before
   using real project information.
5. Capture clean screenshots at 375, 768, and 1440 px, then test Firefox,
   WebKit, keyboard navigation, and screen-reader labels.

## Not tested / blocked

- Any write to the single shared Cloud SQLite database; owner-only reboot;
  cross-session concurrency; invalid/large/malicious upload cases.
- Real Gemini/OpenRouter requests, provider failures/latency, or verification
  of configured secrets and quota dashboards.
- Cloud cold-start from an empty DB, known-sleep wake screen, restart
  persistence, or uploaded-file persistence.
- Full journey through approval, conflict resolution, interview answer,
  claim edit, snapshot release, and acknowledgement.
- Firefox/WebKit; keyboard-only and screen-reader tests; saved screenshot
  files; app logs and Python runtime version.

## Human checklist (owner, about 10 minutes)

1. Open the live URL in a private/incognito browser and on a phone. Record
   loading/wake behavior and capture screenshots with viewport and time.
2. Do not upload real material. Confirm the Upload Sources role-control issue
   before allowing judges to use it.
3. As Reviewer, approve/reject only if you accept changing the shared demo
   state. Then create a release. Switch to Incoming and verify citations and
   acknowledgement. This changes shared state.
4. If testing an interview, use synthetic text, then review the resulting
   pending claim. Do not use real private information.
5. If testing extraction, confirm quota with the owner first. Make at most
   one real call, record the displayed provider/model and elapsed time, and
   stop if any secret or stack trace appears.
6. In Streamlit Cloud, check Manage app → Logs; check only the names (not
   values) of configured secrets; check provider usage dashboards.
7. Reboot only after noting that it may reset the shared app state; re-open
   the app after the owner confirms the reboot.

## Plain-language tool and concept notes

- **Playwright browser:** controls a real browser page the way a person would.
  It was used to visit the deployed app, set viewport widths, select demo
  roles, and read rendered controls. It did not submit any write action.
- **Fresh browser page/context:** starts without relying on an earlier page’s
  role choice. This helps check what a new judge sees. It is not a new database.
- **Streamlit Community Cloud hibernation:** the current official docs say an
  app without traffic for 12 hours sleeps; a visitor sees a wake screen and
  can request that it start. We did not induce sleep, so the deployed screen
  and actual wake time remain unknown.
- **Shared SQLite database:** SQLite stores the demo records in one local DB
  file. The deployed app uses one shared project, so an approval or upload
  could affect other visitors; QA avoided those changes.
- **Viewport width:** the browser’s available page width, used to check
  horizontal overflow at phone/tablet/desktop sizes. Matching widths does not
  prove full mobile usability or accessibility.
- **Direct page URL:** opens a Streamlit multipage route without first clicking
  a sidebar link. It checks routing, not that every workflow is functional.
- **pytest / temporary DB:** pytest runs automated assertions; tests use a
  temporary SQLite file so they cannot write to the live deployment.
- **Fake provider:** test code replaces the real network call with a local
  stand-in, allowing payload masking and failure behavior to be checked
  without sending data or spending API quota.
- **Credential-pattern scan:** checks text for common token shapes and reports
  file locations only. A pattern scan can miss novel credentials and can flag
  synthetic test strings; it is not a guarantee of secret-free history.
- **Git commit timestamp:** records when a commit was created. It is used here
  to compare work with the plan’s stated event window; timestamps were not
  changed.
