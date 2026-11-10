# Disclosures

## AI tools and models

- Copilot-assisted development was used for implementation and QA documentation.
- Gemini model availability was checked for the configured key; extraction is pinned to `gemini-3.6-flash`.
- OpenRouter was tested with one real structured request and is pinned to `deepseek/deepseek-v4.1-flash-1017`.
- The cold-start claim cache contains claim text produced from the packaged demo material. During QA, its source fixture files were aligned with the committed cache and evidence references were narrowed to relevant excerpts. No additional provider request was made for this correction.
- Four real provider calls were used during this approved phase; the maximum was five. The final clean-clone judge journey made no provider call.
- The application may send restricted excerpts to an AI provider during extraction. Read-time filtering does not protect those excerpts from provider prompts.

## Libraries

Runtime dependencies listed in `requirements.txt`: Streamlit, pandas, and `google-genai`.

Development dependency listed in `requirements-dev.txt`: pytest.

## Data

The payment-gateway notes, chat, repository export, task list, and restricted test source are demo fixtures. The restricted fixture contains clearly synthetic values and is not a real credential or contact record. Do not replace it with real sensitive information for a public demo.

## Credentials

The optional secret names are `GEMINI_API_KEY` and `OPENROUTER_API_KEY`. Secret values are intentionally not included in this repository documentation.
