# Changes from the Initial Plan

- The Round 1 plan specified filtering restricted evidence **before sending it to the model**. The implemented version filters restricted sources at read/display time; restricted excerpts can still reach Gemini or OpenRouter during extraction. Moving that filter before model prompts is a Round 3 fix.

- Gemini is the primary extraction provider. OpenRouter was added as a pinned-model fallback (`deepseek/deepseek-v4.1-flash-1017`) instead of automatic model routing.
- The project uses a local heuristic fallback when provider keys are absent or provider requests fail.
- Admin, Reviewer, and Incoming are simulated roles selected in Streamlit; they are not authenticated accounts.
- Cached demo claims and evidence references are included for a cold start. Four existing payment-gateway demo fixture edits were included so a clean clone receives the same source text that supports the cache.
- “Corroborated” is a filename-count label, not a conflict or correctness score.
- Streamlit Community Cloud setup is documented as a trial procedure but was not deployed or verified.
