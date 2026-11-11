# Architecture

## Data flow

1. `app.py` and each multipage script call `database.bootstrap()`.
2. Bootstrap creates or migrates the SQLite schema and seeds demo users and a project. When the database has no sources, chunks, or claims, it parses packaged demo files and seeds cached claims as pending.
3. The Upload Sources page persists accepted `.txt` and `.csv` upload bytes under `uploads/<project_id>/`. The parser creates source-linked excerpts and reparses only selected or unparsed sources.
4. The Review Claims page requests candidate claims from Gemini, then the pinned OpenRouter model, then the labeled local heuristic fallback. Evidence links refer to database chunks.
5. The validator assigns the stored trust status based on linked evidence: no links, one distinct source file, or two or more distinct files.
6. The review functions authorize approve/reject actions, write review and audit rows, and select the actor from the demo role's user row.
7. Retrieval filters sources, chunks, claims, and claim evidence before the pages render them. The Incoming handover includes approved claims only when all linked sources are public.

## SQLite schema

- `users`: seeded demo identities for Admin, Reviewer, and Incoming.
- `projects`: project records, including the demo project.
- `sources`: file metadata and `sensitivity` (`public` or `restricted`).
- `evidence_chunks`: parsed excerpts, source linkage, and chunk indexes.
- `claims`: claim text, type, trust status, review status, and `claim_source` (`generated` or `cached_demo`).
- `claim_evidence`: many-to-many links between claims and evidence chunks.
- `reviews`: approve/reject/edit records with reviewer and timestamp.
- `audit_logs`: allowed and denied review actions with actor, target, action, and timestamp.

`HANDOVERTRAIL_DB` overrides the default `<project directory>/handovertrail.db` path. `bootstrap()` uses `CREATE TABLE IF NOT EXISTS` and additive column migrations, so it can initialize a fresh database or upgrade the known older schema without replacing the database file.

## Permission model

The role selector is a demo control, not authentication. Admin and Reviewer can view all source sensitivities and can review claims. Incoming can view only public material and only approved claims. A claim is omitted when it has no evidence link or any linked chunk belongs to a non-public or unknown source. Evidence excerpts are checked with the same rule.

The handover page reports only the number of approved claims hidden because they reference restricted sources; it does not show their titles or text. Approve/reject functions check permissions before writing. Denied actions are audited.

## Limits and safety notes

- Sensitivity is enforced at retrieval/display time, not before extraction. A provider prompt may contain restricted excerpts.
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
- Provider chain Gemini -> pinned OpenRouter model -> labelled local heuristic, capped at three extractions per session, so a judge never hits a hard failure and the free quota is protected.
- Cached demo claims seeded on first start so the review flow works with no API call.
