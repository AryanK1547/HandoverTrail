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
