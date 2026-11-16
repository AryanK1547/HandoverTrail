# Architecture

## Data flow

1. `app.py` and each multipage script call `database.bootstrap()`.
2. Bootstrap creates or migrates the SQLite schema and seeds demo users and a project. On an empty database it parses packaged demo files and seeds cached claims; synthetic Round 3 sources and claims are added idempotently.
3. The Upload Sources page creates a separate project for an upload workspace. A random workspace token in the URL resolves that project after navigation or refresh; uploads persist under `uploads/<project_id>/`. The parser creates source-linked excerpts and reparses only selected or unparsed sources.
4. Extraction uses the selected project and source IDs, stores run status, avoids duplicates with stable keys, and caps provider input at 80,000 characters.
5. The local conflict detector extracts claim slots, normalizes names and dates, compares claims from separate sources, and records task/decision/risk/single-source gaps. The validator marks claims corroborated only when comparable slot values agree; source count alone is insufficient.
6. Reviewers turn open gaps into draft exit-interview questions. The assigned Departing identity submits an answer that is stored as a timestamped `interview` source, chunked, and extracted from that source only into pending claims.
7. Claim edits append the previous text, editor, edit reason, and time to `claim_versions`, set the claim to edited-pending-review, and write review/audit rows. Approving a linked interview claim resolves its gap.
8. Admin/Reviewer release a versioned JSON snapshot containing only approved claims with evidence exclusively from public sources. SQLite triggers prevent changing or deleting a released snapshot.
9. Incoming reads only the latest release and acknowledges that release's version. Acknowledgements are unique per user/version and are separate from immutable snapshot data.
10. Retrieval filters sources, chunks, claims, and claim evidence before the pages render them. The Incoming role sees interview sources only when all claims linked to that answer are approved; other claims are visible only when approved and every linked source is public.

## SQLite schema

- `users`: seeded demo identities for Admin, Reviewer, and Incoming.
- `projects`: project records, including the demo project.
- `sources`: file metadata, `sensitivity` (`public` or `restricted`), and `source_type` (`source` or `interview`).
- `evidence_chunks`: parsed excerpts, source linkage, and chunk indexes.
- `claims`: claim text, type, trust status, review status, extraction origin, validation time, and an extraction deduplication key.
- `extraction_runs`: latest extraction method, result status, count, source IDs, and completion time per project.
- `claim_evidence`: many-to-many links between claims and evidence chunks.
- `reviews`: approve/reject/edit records with reviewer and timestamp.
- `audit_logs`: allowed and denied review actions with actor, target, action, and timestamp.
- `claim_slots`, `claim_conflicts`, and `gaps`: derived slot values, conflict/corroboration comparisons, and open missing-evidence records.
- `questions` and `answers`: assigned draft/sent questions and timestamped answer records linked to their interview source.
- `user_role_assignments`: additive role assignments, including the demo Departing identity without rebuilding the legacy `users.role` constraint.
- `claim_versions`: append-only snapshots of text replaced during claim edits, with editor, reason, and timestamp.
- `handover_versions`: immutable point-in-time snapshots of approved claims and public citations.
- `handover_acks`: Incoming receipt records attached to one release version.

`HANDOVERTRAIL_DB` overrides the default `<project directory>/handovertrail.db` path. `HANDOVERTRAIL_UPLOADS_DIR` overrides the uploads directory. `bootstrap()` uses additive, idempotent migrations.

The demo project and upload workspaces have different project IDs. Upload
workspaces do not inherit seeded demo claims. The workspace token is an
unguessable URL identifier, not authentication: anyone with the full link can
open the simulated workspace.

## Permission model

The role selector is a demo control, not authentication. Admin and Reviewer can view all source sensitivities and can review claims. Incoming can view only public material and only approved claims. Departing can access only questions tied to the demo Departing user ID and has no access to the project source/claim retrieval functions. A claim is omitted when it has no evidence link or any linked chunk belongs to a non-public or unknown source. Public interview sources are additionally withheld until all linked claims are approved. Common email, phone, credential-like, and long numeric ID values are masked in Incoming claim text and evidence display.

The handover page reports only the number of approved claims hidden because they reference restricted sources; it does not show their titles or text. Approve/reject functions check permissions before writing. Denied actions are audited.

**Deployed QA finding (13 Nov 2026, commit `839953b`):** Retrieval on the Incoming Review and
Upload Sources pages hid the synthetic restricted markers from rendered text
and page markup. However, the Upload Sources page still displayed the file
picker, sensitivity selector, demo-load action, and parse action to Incoming.
The page does not gate these write controls by reviewer role. This is a
permission/UI gap; do not expose real project data to the public demo. The
live Incoming handover also had no released snapshot, so it showed the explicit
empty state rather than live approved claims. Local changes on
`r3/ux-hardening` gate those controls and the candidate-review UI; they are not
in the deployed app yet.

A full browser refresh reset the selected demo role to Admin during QA. Local
changes preserve the simulated role in the URL across navigation and refresh,
but this does not authenticate a person or provide a security boundary.

## Limits and safety notes

- A single provider gateway rejects any non-public chunk and masks common email, phone, credential-like, and long numeric ID patterns before a provider call. Restricted chunks go through local rule-based statement extraction only. Regex masking is conservative pattern matching, not a guarantee that every sensitive value is detected; avoid sending real sensitive data.
- Provider calls are skipped when the selected payload exceeds 80,000 evidence characters; the UI labels the local fallback and gives the reason.
- Incoming display masks the same common value patterns in claims, source names, references, and excerpts. This is a privacy aid, not a replacement for authentication or safe data handling.
- Simulated roles do not establish user identity and must not be used as production authorization.
- Conflict detection supports explicit owner, deadline/date, retry-policy, and decision slot patterns. It is deterministic and local, but cannot infer every natural-language phrasing.
- Date and name normalization reduces formatting differences; similar-but-not-identical subjects are labelled possible conflicts for human review, not treated as certain matches.
- Gaps are rule-based signals, not proof that information is absent from the whole project. They cover tasks without owners, decisions without dates or rationale, risks without mitigation, and single-source claims.
- “Corroborated” means a comparable slot agrees across separate source records; it does not establish source independence or factual correctness.
- `MISSING_EVIDENCE` indicates that a claim has no linked evidence; other gap rules identify specific missing context.
- Releases are immutable SQLite snapshots and include only approved claims that have evidence and whose linked sources are all public. Incoming's acknowledgement is bound to the latest version; a newer release requires a new acknowledgement.
- SQLite and uploads use local filesystem storage. A hosted instance may not retain edits or uploaded files durably.
- Streamlit Community Cloud reboot/restart persistence and the asleep-app wake screen were not tested in this QA run.
- AI output and the cached demo claims require human review. The cached claim source indicates that a claim came from the packaged sample cache.

## Key technical decisions

- Streamlit + SQLite: one language and no servers to host, so one person can build, test and deploy for free. Trade-off: local storage is not durable on hosted instances.
- Claim Ledger as relational tables (claims, claim_evidence, reviews, audit_logs): every claim must link to source excerpts, so unsupported claims show as "Missing evidence" instead of looking like facts.
- One retrieval layer that requires a role for every read: pages cannot fetch data without a role, giving a single place to enforce access.
- Strict visibility rule: Incoming sees a claim only if it is approved and every linked source is public; no partial leaks.
- Read-time authorization is backed by public-only provider prompts and pre-call masking; both checks use the same role/sensitivity rules.
- A single provider gateway for Gemini -> pinned OpenRouter model -> labeled local rule-based fallback keeps public-only filtering and masking at the external-call boundary; extraction remains capped at three runs per session.
- Cached demo claims are seeded in the demo project on first start; upload workspaces remain separate.
- Restricted evidence stays local to the app's rule-based extraction; provider-generated claims cite only the public evidence supplied to the gateway.

## Presentation layer

`ui.py` centralizes the dark-theme CSS, page configuration, role identity, workflow rail, database-backed status guidance, accessible text badges, and footer. `.streamlit/config.toml` owns the base colors; CSS only refines layout and focus states. The app uses native Streamlit page links, tabs, containers, dialogs, status messages, and toasts. Dynamic badge text is HTML-escaped before rendering.
