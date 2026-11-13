# Testing

## Backend suite

Run from the application directory:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests
```

Round 2 baseline: **15 passed**. R3-0 added an additive migration test; the R3-0 result was **16 passed**. The latest R3-1 suite result is **23 passed**. Tests use temporary databases selected through `HANDOVERTRAIL_DB`; they cover sensitivity-aware retrieval, role authorization and audit rows, upload validation/parsing, validator thresholds, and cached demo evidence anchors.

R3-1 coverage adds synthetic-only checks for email, phone, credential-like token, and ID-number masking; both provider gateway paths are replaced with fake functions in tests; restricted chunks are rejected at the gateway; mixed-sensitivity extraction sends only public chunks to a fake provider and handles restricted chunks locally; provider failure falls back locally; and Incoming retrieval masks claim text and public evidence. OpenRouter request construction is tested using a fake HTTP transport. These tests do not make real provider requests.

Streamlit `AppTest` also rendered the landing page and all source/review/handover scripts against a fresh temporary database without app exceptions. Its first default-timeout attempt expired; rerunning each script with a 20-second test timeout passed. This is a local startup/UI smoke check, not a live Cloud test.

## Startup and fresh-clone journey

- A fresh clone of the `qa-fixes` branch started with an empty disposable database. The health endpoint returned HTTP 200 / `ok`.
- Bootstrap loaded the packaged sources and four pending claims before an API request. The landing-page “Load demo project” action confirmed the demo was ready.
- A Reviewer approved one cached public claim. A second synthetic restricted-only claim was approved through the Reviewer permission function in the disposable database.
- After switching to Incoming and navigating from Review Claims to Handover View, the role remained Incoming. The review queue showed only the approved public claim; the handover showed its three public citations and reported one hidden restricted claim without displaying its text.
- A migration check starting from the older `sources` and `claims` schemas confirmed bootstrap added `sensitivity` and `claim_source` and seeded four cached claims.

## Provider checks

Gemini model listing and pinned Gemini/OpenRouter requests were completed earlier in the approved phase. No provider request was made in the final fresh-clone journey or after the 4-of-5 call budget was reached.

## Not run

Streamlit Community Cloud deployment was not attempted. The fresh-clone journey is a local browser check, not a production deployment test.
