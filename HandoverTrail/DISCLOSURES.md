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
- Only synthetic demo data was sent during the provider tests. When users run extraction on custom uploads, those source excerpts can be sent to a provider; restricted excerpts are not filtered before provider prompts.

Testing note: real provider requests during testing were limited to
five; the final clean-clone check used none.

## Libraries

Runtime dependencies listed in `requirements.txt`: Streamlit, pandas, and `google-genai`.

Development dependency listed in `requirements-dev.txt`: pytest.

Third-party packages are installed from the pinned versions recorded in `requirements.txt` and `requirements-dev.txt`.

## Data

The payment-gateway notes, chat, repository export, task list, and restricted test source are demo fixtures. The restricted fixture contains clearly synthetic values and is not a real credential or contact record. Do not replace it with real sensitive information for a public demo.

## Credentials

The optional secret names are `GEMINI_API_KEY` and `OPENROUTER_API_KEY`. Secret values are intentionally not included in this repository documentation.
