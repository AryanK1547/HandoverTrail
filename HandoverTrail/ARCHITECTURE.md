# Architecture

## Data flow

1. `app.py` and each multipage script call `database.bootstrap()`.
2. Bootstrap creates or migrates the SQLite schema and seeds demo users and a project. When the database has no sources, chunks, or claims, it parses packaged demo files and seeds cached claims as pending.
3. The Upload Sources page persists accepted `.txt` and `.csv` upload bytes under `uploads/<project_id>/`. The parser creates source-linked excerpts and reparses only selected or unparsed sources.
4. The Review Claims page sends public evidence to the provider gateway, which masks contact, credential-like, and long ID-number-like values before sending it to Gemini or the pinned OpenRouter model. Restricted evidence is never sent to either provider and is processed only by the local heuristic.
5. The validator assigns the stored trust status based on linked evidence: no links, one distinct source file, or two or more distinct files.
6. The review functions authorize approve/reject actions, write review and audit rows, and select the actor from the demo role's user row.
7. Retrieval filters sources, chunks, claims, and claim evidence before the pages render them. The Incoming handover includes approved claims only when all linked sources are public.

## SQLite schema

- `users`: seeded demo identities for Admin, Reviewer, and Incoming.
- `projects`: project records, including the demo project.
- `sources`: file metadata, `sensitivity` (`public` or `restricted`), and `source_type`.
- `evidence_chunks`: parsed excerpts, source linkage, and chunk indexes.
- `claims`: claim text, type, trust status, review status, and `claim_source` (cached demo or the extraction method).
- `claim_evidence`: many-to-many links between claims and evidence chunks.
- `reviews`: approve/reject/edit records with reviewer and timestamp.
- `audit_logs`: allowed and denied review actions with actor, target, action, and timestamp.
- Round 3 scaffolding: empty `claim_versions`, `claim_slots`, `gaps`, `questions`, `answers`, `handover_versions`, `handover_acks`, and `user_role_assignments` tables. Their feature behavior is not implemented yet.

`HANDOVERTRAIL_DB` overrides the default `<project directory>/handovertrail.db` path. `bootstrap()` uses `CREATE TABLE IF NOT EXISTS` and additive column migrations, so it can initialize a fresh database or upgrade the known older schema without replacing the database file.

## Permission model

The role selector is a demo control, not authentication. Admin and Reviewer can view all source sensitivities and can review claims. Incoming can view only public material and only approved claims. A claim is omitted when it has no evidence link or any linked chunk belongs to a non-public or unknown source. Evidence excerpts are checked with the same rule. Common email, phone, credential-like, and long numeric ID values are additionally masked in Incoming claim text and evidence display.

The handover page reports only the number of approved claims hidden because they reference restricted sources; it does not show their titles or text. Approve/reject functions check permissions before writing. Denied actions are audited.

## Limits and safety notes

- A single provider gateway rejects any non-public chunk and masks common email, phone, credential-like, and long numeric ID patterns before a provider call. Restricted chunks go through the local heuristic only. Regex masking is conservative pattern matching, not a guarantee that every sensitive value is detected; avoid sending real sensitive data.
- Incoming display masks the same common value patterns in claims, source names, references, and excerpts. This is a privacy aid, not a replacement for authentication or safe data handling.
- Simulated roles do not establish user identity and must not be used as production authorization.
- “Corroborated” measures distinct supporting filenames only. It does not detect disagreement, source independence, or factual correctness.
- `MISSING_EVIDENCE` indicates that a claim has no linked evidence; the app does not perform broader claim-completeness or conflict analysis.
- SQLite and uploads use local filesystem storage. A hosted instance may not retain edits or uploaded files durably.
- AI output and the cached demo claims require human review. The cached claim source indicates that a claim came from the packaged sample cache.

## Key technical decisions

- Streamlit + SQLite: one language and no servers to host, so one person can build, test and deploy for free. Trade-off: local storage is not durable on hosted instances.
- Claim Ledger as relational tables (claims, claim_evidence, reviews, audit_logs): every claim must link to source excerpts, so unsupported claims show as "Missing evidence" instead of looking like facts.
- One retrieval layer that requires a role for every read: pages cannot fetch data without a role, giving a single place to enforce access.
- Strict visibility rule: Incoming sees a claim only if it is approved and every linked source is public; no partial leaks.
- Read-time filtering first because it can be tested deterministically; filtering before provider prompts is the first Round 3 task.
- A single provider gateway for Gemini -> pinned OpenRouter model -> labelled local heuristic keeps public-only filtering and masking at the external-call boundary; extraction remains capped at three runs per session.
- Cached demo claims seeded on first start so the review flow works with no API call.
- Restricted evidence stays local to the app's heuristic extraction; provider-generated claims cite only the public evidence supplied to the gateway.
