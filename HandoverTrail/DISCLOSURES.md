# Disclosures

## AI tools and models

AI assistance in building the project:
- Gemini (Google chat assistant) was used to write the first version of
  the basic application architecture and code.
- GitHub Copilot (Copilot SDK in VS Code) was used to refine, fix and
  extend that code, and to produce the QA tests and documentation.
- Claude (Anthropic chat assistant) was used for planning: drafting the
  Round 1 plan and the QA instructions, and reviewing test results and
  documentation.
- Round 3: AI coding agents (GitHub Copilot and Claude, including Claude Code,
  Anthropic's coding agent) were used under the participant's direction to
  implement, test, and document the Round 3 work from the participant's
  plan (`ROUND3_MASTER_PLAN.md`). The final user-experience pass was written
  with Claude Code: the guided tour, the redesigned Review page and its
  evidence-match check, the Day 1 / Week 1 / Month 1 pick-up plan, private
  demo copies, the browser journeys added with them, the README, the
  Round 2 to Round 3 comparison, the README screenshots, and the final
  project PDF (generated with the ReportLab Python library). Claude Code also
  drove the live site in a scripted browser on 16 Nov 2026 to verify it.
- All generated code and text was reviewed by the participant, who is
  responsible for the submission.

AI models used inside the product (free-tier APIs):
- Gemini API, model gemini-3.6-flash: primary claim extraction.
- OpenRouter API, pinned model deepseek/deepseek-v4.1-flash-1017:
  fallback extraction.
- No model is used for conflict and gap detection, exit-interview
  questions, interview-answer extraction, verification and evidence-match
  checks, or the pick-up plan; these are local deterministic rules.
- The provider gateway sends only public-sensitivity excerpts, after masking common emails, phone numbers, credential-like tokens, and long numeric ID patterns. Restricted excerpts are kept out of provider prompts and handled only by the local heuristic. Regex masking can miss unusual formats; do not use the demo role selector as authentication or send real sensitive data.

The Round 3 deployed QA run on 13 Nov 2026 did not make a live provider
request. `gemini-3.6-flash` and
`deepseek/deepseek-v4.1-flash-1017` are the configured model identifiers
documented by the application; Phase D did not verify which provider/model
would answer a live request or whether the Cloud secrets are configured.

Testing note: real provider requests during Round 2 testing were limited to
five. Round 3 tests use fake providers and make no real provider requests.
No real provider request was made during the 13 Nov 2026 Phase D browser check
or the 16 Nov 2026 live-site check (commit `106d76e`); the latter deliberately
did not run extraction, to protect the free-tier quota, so live provider
responses remain unverified.

## Libraries

Runtime dependencies listed in `requirements.txt`: Streamlit, pandas, and `google-genai`.

Development dependency listed in `requirements-dev.txt`: pytest.

Third-party packages are installed from the pinned versions recorded in `requirements.txt` and `requirements-dev.txt`.

The browser-test dependency `@playwright/test` is pinned in
`package.json`/`package-lock.json`. Playwright drives Chromium to perform
multi-page user journeys, which catches browser-visible navigation and
interaction issues that backend tests cannot see. Its runner creates temporary
database/upload storage and disables provider calls; Node.js and npm are
needed only for this browser-test command. The same tool was used outside the
repository's test suite to capture the README screenshots and to run the
16 Nov 2026 live-site check.

The final project PDF was produced with ReportLab, Pillow, and pypdf in a
temporary environment outside the repository; they are not runtime or test
dependencies of the app.

## Data

The payment-gateway notes, chat, repository export, task list, and restricted test source are demo fixtures. The restricted fixture contains clearly synthetic values and is not a real credential or contact record. Do not replace it with real sensitive information for a public demo. The Round 3 conflict and gap fixtures (`r3_conflicts_a.txt`, `r3_conflicts_b.txt`, `r3_gaps.txt`) are synthetic as well, as are all interview answers and screenshots in the documentation.

## Credentials

The optional secret names are `GEMINI_API_KEY` and `OPENROUTER_API_KEY`. Secret values are intentionally not included in this repository documentation.
