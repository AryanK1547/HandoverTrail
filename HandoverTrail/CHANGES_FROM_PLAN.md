# Changes from the Initial Plan

- The delivered application uses the existing Streamlit multipage stack rather than introducing a separate web framework.
- SQLite and local filesystem uploads are the implemented storage path. Optional Supabase/PostgreSQL support is not implemented.
- Gemini is the primary extraction provider. OpenRouter was added as a pinned-model fallback (`deepseek/deepseek-v4.1-flash-1017`) instead of automatic model routing.
- The project uses a local heuristic fallback when provider keys are absent or provider requests fail.
- Admin, Reviewer, and Incoming are simulated roles selected in Streamlit; they are not authenticated accounts.
- Cached demo claims and evidence references are included for a cold start. Four existing payment-gateway demo fixture edits were included so a clean clone receives the same source text that supports the cache.
- Source sensitivity is filtered during retrieval and display, not before extraction-provider prompts are assembled.
- “Corroborated” is a filename-count label, not a conflict or correctness score.
- Streamlit Community Cloud setup is documented as a trial procedure but was not deployed or verified.
