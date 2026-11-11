# Changes from the Initial Plan

- The Round 1 plan specified filtering restricted evidence **before sending it to the model**. The implemented version filters restricted sources at read/display time; restricted excerpts can still reach Gemini or OpenRouter during extraction. Moving that filter before model prompts is a Round 3 fix.

- The delivered stack is Streamlit with SQLite and local filesystem uploads. Optional Supabase/PostgreSQL support is not implemented.
- Gemini is the primary extraction provider. OpenRouter was added as a pinned-model fallback (`deepseek/deepseek-v4.1-flash-1017`) instead of automatic model routing.
- The project uses a local heuristic fallback when provider keys are absent or provider requests fail.
- Admin, Reviewer, and Incoming are simulated roles selected in Streamlit; they are not authenticated accounts.
- Cached demo claims and evidence references are included for a cold start. Four existing payment-gateway demo fixture edits were included so a clean clone receives the same source text that supports the cache.
- Source sensitivity is filtered during retrieval and display, not before extraction-provider prompts are assembled; this is a known plan deviation for Round 3.
- “Corroborated” is a filename-count label, not a conflict or correctness score.
- Streamlit Community Cloud setup is documented as a trial procedure but was not deployed or verified.
