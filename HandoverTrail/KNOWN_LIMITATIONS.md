# Known Limitations

## Live-demo risks

The findings in this section describe deployed commit `839953b` as checked on
13 Nov 2026. The `r3/ux-hardening` worktree contains local mitigations, but it
has not been pushed or deployed; the public URL still runs the previously
checked code.

- **The demo role selector is not authentication.** Anyone can select Admin or
  Reviewer. A full browser refresh reset the selected role to Admin in the
  13 Nov 2026 deployed check.
- **Incoming sees write controls on Upload Sources.** The deployed UI exposed
  file upload, sensitivity choice, demo registration, and parsing controls to
  Incoming. The page does not gate those actions by role. They may change data
  shared by all visitors. Do not upload real project or personal information.
- **The first Incoming handover is empty until released.** On the observed
  deployed state, 13 claims were pending and there was no released snapshot.
  Incoming saw the page's explicit “No handover has been released yet” state.
- **Live provider behavior is not verified by Phase D.** The interface
  indicated Gemini was available, but this QA made no Gemini/OpenRouter
  request. Configured model names are not evidence of a successful live call.
- **Upload size messaging conflicts.** The Upload Sources page says 2 MB per
  file while the widget says 200 MB per file. Live rejection behavior was not
  tested.
- Streamlit's app UI logged one unidentified 404 resource on page loads and an
  aborted third-party analytics request. The source of the 404 was not
  identified; no app traceback was observed.

## Product and deployment limits

- The app has no authenticated accounts or private per-user workspace. The
  demo project uses one shared SQLite database for all visitors. Local upload
  workspaces isolate their project data by a random URL token, but anyone with
  the link can open that workspace.
- SQLite and uploaded files live on the app's local filesystem. Streamlit
  Community Cloud storage is not durable; a restart or instance replacement
  may lose changes and uploads. Reboot persistence was not tested.
- Streamlit's current Community Cloud documentation says apps without traffic
  for 12 hours sleep and visitors see a wake-up page. The live app was not
  observed asleep, so its screen and actual wake time were not tested.
- Incoming visibility rules filter retrieved claims and evidence, but the
  visible upload controls described above are not role-gated. Do not rely on
  the role selector for confidentiality or authorization.
- Provider masking uses patterns for common contacts, credential-like strings,
  and long numeric identifiers. Pattern-based masking can miss other formats.
- Provider extraction has an 80,000-character evidence limit. Larger selected
  input skips external providers and uses the labeled local rule-based
  extractor. It preserves explicitly matched source statements, but can miss
  indirectly phrased claims that a provider might have found.
- Conflict, corroboration, and gap analysis is rule-based. It can miss
  differently worded facts, and a “Corroborated” label does not prove that
  sources are independent or factually correct.
- Interview question wording uses local templates. Interview answers are
  processed locally into pending claims; the live question/answer lifecycle
  was not exercised in Phase D.
- No live approval, rejection, upload, manual conflict resolution, interview,
  release, acknowledgement, real provider request, restart, or cross-session
  mutation was performed in Phase D. Opening Review Claims as Admin/Reviewer
  does automatically recalculate and persist derived conflict/gap records.
- Browser verification used Chromium only. Firefox, WebKit, keyboard-only
  flows, and screen-reader behavior remain unverified.
- Local Playwright covers two upload workspaces in sequence, not simultaneous
  concurrent users. It runs against temporary local SQLite storage, not
  Streamlit Community Cloud.
