# Testing

## Backend suite

Run from the application directory:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests
```

Round 2 baseline: **15 passed**. R3-0 added an additive migration test; the R3-0 result was **16 passed**. R3-1 passed **23 tests**; the R3-UI suite passed **25 tests**. R3-2 passed **30 tests**; R3-3 passes **32 tests**. Tests use temporary databases selected through `HANDOVERTRAIL_DB`; they cover sensitivity-aware retrieval, role authorization and audit rows, upload validation/parsing, cached demo evidence anchors, badge HTML escaping, UI contrast-token thresholds, conflict/gap rules, exit-interview lifecycle, and audited actions.

R3-1 coverage adds synthetic-only checks for email, phone, credential-like token, and ID-number masking; both provider gateway paths are replaced with fake functions in tests; restricted chunks are rejected at the gateway; mixed-sensitivity extraction sends only public chunks to a fake provider and handles restricted chunks locally; provider failure falls back locally; and Incoming retrieval masks claim text and public evidence. OpenRouter request construction is tested using a fake HTTP transport. These tests do not make real provider requests.

Streamlit `AppTest` also rendered the landing page and all source/review/handover scripts against a fresh temporary database without app exceptions. Its first default-timeout attempt expired; rerunning each script with a 20-second test timeout passed. This is a local startup/UI smoke check, not a live Cloud test.

R3-2 uses deterministic local comparisons: owner/name case and punctuation are normalized, common full and partial dates are normalized, and similar subject text with differing values is marked **Possible conflict** instead of a definite conflict. Tests cover disagreeing owners, agreeing normalized names/dates, missing task owners, missing decision dates/rationale, missing risk mitigation, single-source claims, and a resolution audit row. No LLM or network requests are used by these tests.

An isolated AppTest bootstrapped a fresh database and rendered the Review Claims page with all three synthetic disagreements, their citations, and resolution buttons. The first R3-2 full-suite run exposed two old cold-start count assertions; the packaged demo now intentionally includes eight sources, 17 evidence chunks, and 13 cached pending claims, and the assertions were updated. The final full suite and checks are recorded in `QA_SESSION_LOG.md`.

R3-3 tests cover template generation for every gap type, idempotent regeneration, reviewer add/edit/delete/send actions, per-user question isolation, public interview-source withholding until approval, answer authorship/timestamp/sensitivity, source chunking, scoped extraction that preserves old claims, pending review status, and resolution after approval. Interview extraction is forced through the local heuristic in tests; the provider functions are replaced with fail-fast fakes, so tests cannot make real provider calls. AppTest rendered the page for both Reviewer and Departing roles with no exceptions.

The UI snapshot set is in `qa/ui/`: `before-375.png`, `before-768.png`, `before-1440.png`, and matching `after-*.png` files. At all three viewport widths the document and body widths matched the viewport width. At 375 px the saved screenshot has the Streamlit sidebar open because the browser viewport was resized from desktop; the navigation drawer must be collapsed to see the page content. The mobile rail collapsed to a single step label.

## Startup and fresh-clone journey

- A fresh clone of the `qa-fixes` branch started with an empty disposable database. The health endpoint returned HTTP 200 / `ok`.
- Bootstrap loaded the packaged sources and cached pending claims before an API request. After R3-2, a fresh database contains eight sources, 17 evidence excerpts, and 13 cached pending claims. The landing-page “Load demo project” action confirmed the demo was ready.
- A Reviewer approved one cached public claim. A second synthetic restricted-only claim was approved through the Reviewer permission function in the disposable database.
- After switching to Incoming and navigating from Review Claims to Handover View, the role remained Incoming. The review queue showed only the approved public claim; the handover showed its three public citations and reported one hidden restricted claim without displaying its text.
- A migration check starting from the older `sources` and `claims` schemas confirmed bootstrap added `sensitivity` and `claim_source`; the additive Round 3 schema and synthetic fixture seeding are also covered by pytest.

## Provider checks

Gemini model listing and pinned Gemini/OpenRouter requests were completed earlier in the approved phase. No provider request was made in the final fresh-clone journey or after the 4-of-5 call budget was reached.

## Not run

Streamlit Community Cloud deployment was not attempted. The fresh-clone journey is a local browser check, not a production deployment test.
