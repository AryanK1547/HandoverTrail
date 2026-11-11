# Known Limitations

- The role selector is simulated and provides no authentication, identity proof, or per-user session isolation.
- Restricted source content is filtered when retrieved for display, but may be included in Gemini or OpenRouter extraction prompts.
- The validator does not detect contradictory claims or determine whether evidence is independent. “Corroborated” only means two or more distinct source files are linked.
- The cached demo claims are examples and still require human review.
- The three-extraction cap is per Streamlit browser session, not a durable user or service quota.
- SQLite and uploads are local files. Streamlit Community Cloud persistence was not verified, and local files may be lost when the service replaces an instance.
- No production deployment, external database, real authentication provider, automated redaction, or version history is implemented.
