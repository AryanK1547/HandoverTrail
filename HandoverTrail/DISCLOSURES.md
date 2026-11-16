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
- All generated code and text was reviewed by the participant, who is
  responsible for the submission.

AI models used inside the product (free-tier APIs):
- Gemini API, model gemini-3.6-flash: primary claim extraction.
- OpenRouter API, pinned model deepseek/deepseek-v4.1-flash-1017:
  fallback extraction.
- The provider gateway sends only public-sensitivity excerpts, after masking common emails, phone numbers, credential-like tokens, and long numeric ID patterns. Restricted excerpts are kept out of provider prompts and handled only by the local heuristic. Regex masking can miss unusual formats; do not use the demo role selector as authentication or send real sensitive data.

The Round 3 deployed QA run on 13 Nov 2026 did not make a live provider
request. `gemini-3.6-flash` and
`deepseek/deepseek-v4.1-flash-1017` are the configured model identifiers
documented by the application; Phase D did not verify which provider/model
would answer a live request or whether the Cloud secrets are configured.

Testing note: real provider requests during Round 2 testing were limited to
five. Round 3 tests use fake providers and make no real provider requests.
No real provider request was made during the 13 Nov 2026 Phase D browser check.

## Libraries

Runtime dependencies listed in `requirements.txt`: Streamlit, pandas, and `google-genai`.

Development dependency listed in `requirements-dev.txt`: pytest.

Third-party packages are installed from the pinned versions recorded in `requirements.txt` and `requirements-dev.txt`.

The browser-test dependency `@playwright/test` is pinned in
`package.json`/`package-lock.json`. Playwright drives Chromium to perform
multi-page user journeys, which catches browser-visible navigation and
interaction issues that backend tests cannot see. Its runner creates temporary
database/upload storage and disables provider calls; Node.js and npm are
needed only for this browser-test command.

## Data

The payment-gateway notes, chat, repository export, task list, and restricted test source are demo fixtures. The restricted fixture contains clearly synthetic values and is not a real credential or contact record. Do not replace it with real sensitive information for a public demo.

## Credentials

The optional secret names are `GEMINI_API_KEY` and `OPENROUTER_API_KEY`. Secret values are intentionally not included in this repository documentation.
