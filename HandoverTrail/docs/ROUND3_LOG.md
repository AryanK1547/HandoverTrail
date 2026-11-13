# Round 3 Work Log

- Round 3 window: 23:59 IST Friday, 13 November 2026 through 23:59 IST Monday, 16 November 2026.
- Round 2 baseline tag: `round2-submitted` at commit `87b7c2b24826cb8917683edaf197059c109d51c0`.
- Round 3 setup branch: `r3/setup`, created from the tagged baseline. This branch has not been pushed.

## R3-1 provider-safe extraction and masking

- R3-1 work branch: `r3/provider-safe`, based on the R3-0 setup commit. It has not been pushed.
- Implemented the provider gateway as the only module that calls Gemini or OpenRouter. It refuses chunks unless sensitivity is explicitly `public`, masks excerpt and citation metadata before composing the prompt, and reports the number of masked values.
- Restricted chunks use local keyword heuristics only. Each stored claim carries its extraction method in `claim_source`; the Review UI displays it and reports the mask count.
- Incoming retrieval masks common personal/contact or credential-like values in approved claim text, visible filenames, references, and excerpts.
- Tests use monkeypatched fake provider functions, which replace the network boundary with controlled responses so payload handling is checked without sending requests or incurring API usage. The complete suite passed 23 tests; compileall, empty-database startup, and local page smoke checks passed.
- The masking patterns use Python `re`, a built-in library for matching text shapes. This avoids adding a dependency; patterns target common emails, phone formats, key-like tokens, and long numeric IDs, but are not a guarantee of detecting every sensitive value.
- A first short AppTest attempt hit its default three-second timeout; all four page scripts passed when rerun with a 20-second test timeout. A fallback test also exposed and fixed a decision-keyword matching gap.
- No real provider requests were made. Live provider behavior and Streamlit Cloud behavior remain unverified.

## R3-UI design system and workflow orientation

- R3-UI work branch: `r3/ui`, based on `r3/provider-safe`; no push.
- Added centralized `ui.py` helpers for page setup, theme CSS, role identity, workflow links and real counts, database-derived next-step guidance, badges, empty states, metrics, glossary, and version footer. Added `.streamlit/config.toml` for the dark base theme and minimal toolbar; no secrets file was changed.
- Restyled the landing page, source upload page, claim review page, handover page, and the legacy `handover.py` view using native Streamlit components. Business rules and database schema were not changed. Review claims now have separate trust/review/origin badges, reject confirmation, saved-action toasts, and truthful extraction status updates. Incoming handover explains hidden approved items.
- Plain-language concepts: design tokens are named color choices reused across the interface; `config.toml` sets Streamlit's base theme while a single CSS block handles layout and focus refinements; `data-testid` selectors identify pinned Streamlit components for styling; contrast ratio measures text readability against a background; `html.escape` converts angle brackets into text so dynamic badge labels cannot become HTML or script.
- Contrast verification covers all configured foreground/background pairs. The smallest measured pair is the theme text color on the primary indigo (`#E6EBF5` on `#5558D9`) at 4.64:1, above the 4.5:1 target. The original indigo was slightly adjusted because it did not meet that threshold with the configured text color.
- Test result: full suite passed 25 tests, including the new token-contrast and badge-escaping tests. Python compileall passed. AppTest passed for the app entrypoint and each page using Streamlit's multipage navigation context; direct AppTest execution of a page alone cannot resolve multipage links, so the final smoke check used the app entrypoint. Streamlit 1.67.0 provides `page_link`, `popover`, `status`, `dialog`, and `toast`.
- Material icon token labels rendered as literal icon names in the first browser check, so they were removed rather than leaving overlapping labels. The workflow links keep explicit text labels; badges use a simple symbol plus readable status text.
- Local browser check: `/_stcore/health` returned `ok`. Before/after screenshots are saved in `qa/ui/` at 375, 768, and 1440 px. At each width document/body widths equaled viewport width; the 375 px rail collapsed to the current step. The 375 px screenshot was captured after resizing a desktop browser with the sidebar expanded, so the navigation drawer occupies the view until collapsed.
- No real Gemini or OpenRouter calls were made. The app UI displayed whether a provider was configured, without displaying any key. No secrets were printed.

## R3-2 conflict and missing-evidence detection

- Work branch: `r3/conflicts`, based on `r3/ui`; not pushed.
- Added idempotently seeded synthetic conflicts for owner, release date, and retry policy, plus task-owner, decision-date/rationale, risk-mitigation, and single-source gaps.
- Added local claim-slot extraction, name/date normalization, definite and possible conflict classifications, and corroboration only when normalized values agree across separate sources. Conflict detection requires no provider call.
- Added side-by-side comparison cards with evidence citations and audited reviewer resolution actions. Open evidence gaps are shown with their related claim and evidence.
- The validator now reports `VERIFIED` only when normalized claim slots agree. Two source links by themselves remain `SINGLE_SOURCE`.
- Plain-language concepts: slots make claims comparable; normalization makes formats such as `15 Nov 2026` and `2026-11-15` equivalent; similar text is only a possible match; SQLite's stable IDs prevent duplicate gap rows on repeated scans; audit rows preserve review decisions.
- Verification: full suite **30 passed**; compileall, `git diff --check`, and fresh-database Streamlit AppTest passed. Tests use synthetic fixtures and make no provider calls.
