# ROUND 3 MASTER PLAN: HandoverTrail (Techtones, solo: Aryan Khode)

Hackathon: CodersInPune. Round 3 clock: **opens 23:59 IST Fri 13 Nov 2026, closes 23:59 IST Mon 16 Nov 2026.**
No late window. Missing the deadline ends the event.

> **How to use this file.** It is a plan, not code. Planning before the clock opens is allowed.
> **Do not write or commit feature code for the three improvements before 23:59 IST on Fri 13 Nov.**
> The agent prompts in section 8 must only be run AFTER the window opens.
> Keep `AGENT_QA_BRIEF.md` and `AGENT_QA_BRIEF_DEPLOYED.md` in the repo; their rules still apply
> (evidence only, never print secrets, synthetic data only, explain every tool and concept, keep a session log).

---

## 1. Rules that shape the plan (from the official event page)

1. Only work done inside the window counts. Judges may ask for commit history. **Do not rewrite or squash history.**
2. The **three improvements named in Round 2 are what Round 3 is measured against.** Deliver exactly these, fully.
3. Every participant files their own entry (role + what you built, in your own words). A missing entry = no certificate.
4. Finalists must have reserved their seat (payment where applicable) AND make a valid Round 3 submission.
5. Disclose significant AI tools again (Gemini, GitHub Copilot, Claude, in-product Gemini and OpenRouter).
6. A judge must be able to open the live link and verify. Anything unverifiable does not count.
7. Submission contents: final working link, public repo, updated project PDF, completed-improvements list,
   technical details, testing notes, team-member contributions (exact form arrives per the official timeline).

### Round 3 scoring (from the Round 1 brief) and what it means for us
| Criterion | Pts | What we must show |
|---|---|---|
| Completeness of the product | 25 | The whole workflow works from start to finish, including the new parts |
| Improvements delivered | 20 | The 3 promised improvements are present, working and visibly better than Round 2 |
| Reliability under normal use | 20 | Missing information, bad input and provider failures never mislead the user |
| Usability and real-world fit | 20 | A new person can complete a handover and continue the work with little help |
| Documentation and roadmap | 15 | Clear README, setup, limitations, testing notes, honest roadmap |

---

## 2. The three promised improvements (exact wording from Round 2; do not change the promise)

1. **Conflict and missing-evidence detection.** Compare claims across sources for incompatible owners, dates or decisions; separate genuine conflicts from simple corroboration; flag missing owners, dates and decisions; show both versions side by side with citations.
2. **Gap-to-question exit interview.** Turn detected gaps into a short, editable question list for the departing person. Answers are saved as new evidence with an owner and timestamp and go through the normal review workflow.
3. **Provider-safe, accountable handover.** Role-scoped extraction so restricted excerpts are never sent to a provider, plus masking of secrets and personal contacts before any model call; version history for approved handovers; and an acknowledgement that records which version the incoming person received. (Round 2 PDF also states claim editing will arrive together with version history.)

---

## 3. Time plan (IST). Solo builder: assume about 12 productive hours per day

| When | Work | Notes |
|---|---|---|
| Thu 12 - Fri 13 (BEFORE the window) | Non-code prep only: confirm and pay for the seat, tag the Round 2 baseline, read this plan, design on paper, check accounts and API quotas | See section 4 |
| Fri 23:59 - Sat 03:00 | **R3-0** setup: branch, baseline tests green, schema migration scaffold | Then sleep |
| Sat day | **R3-1** provider-safe extraction + masking, then **R3-UI** design system (about 3.5 h, see `ROUND3_UI_DESIGN_SPEC.md`), then **R3-2** conflict + missing-evidence detection | R3-1 first: small, valuable, de-risks the rest. R3-UI before R3-2 so every new page is built on the design system |
| Sun day | **R3-3** gap-to-question exit interview, then **R3-4** claim editing + version history | R3-3 depends on gaps from R3-2 |
| Mon morning | **R3-5** handover release + acknowledgement | |
| **Mon 12:00 FEATURE FREEZE** | No new features after this | Protects reliability and docs |
| Mon 12:00 - 18:00 | Live-site QA, bug fixes, final PDF, README/docs, own entry | Use `AGENT_QA_BRIEF_DEPLOYED.md` |
| **Mon 18:00 TARGET SUBMIT** | Submit with 6 hours of buffer | Hard deadline is 23:59 |
| Stretch (only if everything above is done and tested) | R3-6 per-visitor workspace; R3-7 Day-1/Week-1/Month-1 plan | Never at the cost of the three promises |

If a block overruns, **cut stretch items first, then polish, never the testing and docs block.**

---

## 4. What you can do BEFORE the window opens (allowed, and important)

1. **Confirm and pay for your seat.** Seats not confirmed and paid within 12 hours of the mail roll over to the next teams. Do this first.
2. **Tag the baseline** (this is bookkeeping, not building). From the repo root:
   `git switch main`, `git pull`, `git tag round2-submitted`, `git push origin round2-submitted`.
   A tag is a permanent label on a commit. It gives judges a clear "before" snapshot, so Round 3 work is visibly separate.
3. **Check your Round 2 history** with `git log --format="%h %ad %s" --date=iso`. Note any commit before Sun 8 Nov 10:00 IST. Do not alter history; be ready to explain.
4. **API quotas:** check Google AI Studio and OpenRouter dashboards for remaining limits. Plan to cache LLM outputs so demos never depend on quota.
5. **Design on paper only:** data model changes (section 5), screens, prompts, test lists. Do NOT write feature code, fixtures or migrations yet.
6. **Environment:** make sure Python, VS Code, GitHub login and the Streamlit Cloud login work on your laptop.
7. **Rest.** The window is 72 hours of continuous clock time; sleep is part of the plan.

---

## 5. Design of each improvement (concepts explained)

### R3-1 Provider-safe extraction and masking (build FIRST)
**Goal:** restricted text is never sent to Gemini or OpenRouter; secrets and personal contacts are masked in anything that is.
- **Concept, "choke point".** Put one function in one file through which every provider request must pass, e.g. `build_provider_payload(chunks)`. If there is a single door, you can guard it and test it. No other code may call a provider directly.
- **Rule:** the payload may contain only chunks from sources with `sensitivity = public`. Chunks from restricted sources are processed only by the local heuristic, or skipped for AI extraction. If a restricted chunk reaches the choke point, **raise an error**, do not silently drop it.
- **Masking:** replace emails, phone numbers (Indian and international formats), API-key-like tokens (long random strings, known prefixes such as `AIza`, `sk-`), and ID-number-like digit runs with placeholders like `[REDACTED:phone]`. Concept: a **regular expression (regex)** is a pattern describing text shapes. Masking is deliberately conservative: it prefers hiding too much over leaking.
- **Read-time masking:** the Handover View for Incoming also shows masked excerpts, so contacts that were meant for reviewers only are not exposed.
- **UI:** the Review page shows "X values masked before AI call" and a clear label of which method produced each claim.
- **Acceptance tests:** a fake provider captures every payload; assert the synthetic fake secret and fake phone never appear; assert a restricted chunk reaching the choke point raises; assert masking patterns catch a table of examples and do not mangle normal text; assert provider failure falls back correctly.

### R3-2 Conflict and missing-evidence detection
**Goal:** reviewers see where sources disagree and what is missing, with both versions and citations.
- **Concept, "slots".** Think of a claim as `subject + attribute + value`, e.g. (payment webhook, owner, "Priya"). Two claims **conflict** when they describe the same subject and attribute with different values from different sources. Extract slots with the LLM (cached) or a rule-based fallback; **do the comparison with ordinary, deterministic code** so it is testable and not a guess.
- **Normalisation:** lower-case, strip punctuation, normalise dates ("15 Nov", "2026-11-15"), match names and subjects loosely (simple similarity). Concept: **precision vs recall**. Too eager = false conflicts that annoy reviewers; too shy = missed conflicts. Label uncertain matches "Possible conflict".
- **Status:** use the existing `CONFLICTING` state. "Corroborated" now means sources **agree**, not just two filenames.
- **Missing-evidence checklist:** open tasks without an owner, decisions without a date or rationale, risks without a mitigation, claims with one source only. Each becomes a **gap record** linked to the claim or subject.
- **UI:** a "Conflicts and gaps" panel; side-by-side Version A / Version B with citations; the reviewer resolves (keep A, keep B, keep both as context, mark unresolved). Resolutions are audited.
- **Data:** deliberately create synthetic demo sources that contain 2 or 3 conflicts and several gaps (inside the window).
- **Acceptance tests:** conflict found for differing owners; not flagged when values agree after normalisation; date normalisation cases; gap rules; resolution is audited; no LLM needed for the comparison tests.

### R3-3 Gap-to-question exit interview
**Goal:** close gaps while the departing person is still reachable.
- Add a role **Departing** (can see only the questions assigned to them and submit answers).
- **Question generator:** from each open gap, produce a question using templates ("Who now owns X, and where is it documented?"); optional LLM rewording (cached, masked payload only). The reviewer can **edit, delete or add** questions, then "send to leaver".
- **Answers** are saved as a **new source** of type `interview` with author, timestamp and a sensitivity choice, split into evidence chunks, then claims extracted from that source only (through the safe choke point) arrive as **pending claims** in the normal review workflow.
- **Gap closure:** a gap is marked "answered, pending review" when a new claim links to the answer, and "resolved" after approval.
- **Acceptance tests:** question created from each gap type; answer stored with author and timestamp; answer-derived claims start pending; Departing cannot see other sources or claims; Incoming cannot see unapproved answers.

### R3-4 Claim editing and version history
- **Edit:** Reviewer/Admin can edit claim text. Each edit creates a row in `claim_versions` (claim_id, version, text, editor, time, reason). **Concept, "append-only history":** old versions are never overwritten, so changes are traceable.
- Editing an approved claim returns it to Pending (human approval is always required).
- UI: "History" expander on each claim showing versions and who changed what.
- **Acceptance tests:** edit creates a new version; approved + edit = pending; history order correct; Incoming never sees unapproved edits.

### R3-5 Handover release and acknowledgement
- **Release:** Reviewer/Admin clicks "Release handover". The app saves a **snapshot** (`handover_versions`: version number, time, released_by, JSON of approved claims and citation references). Incoming sees the latest release.
- **Acknowledgement:** Incoming clicks "I have received version N" -> row in `handover_acks` (user, version, time). The release shows "Acknowledged by ... at ...". Re-acknowledging an older version is blocked or clearly labelled.
- **Acceptance tests:** release creates a snapshot; later edits do not change the released snapshot; new release increments the version; acknowledgement stored once per version; only Incoming can acknowledge.

### Bonus features (see `ROUND3_BONUS_GIT_HANDOVER.md`)
Flagship bonus: **Git Handover** (deterministic leaver footprint and knowledge-at-risk analysis from git history, feeding the Claim Ledger and the exit interview). Two cheap multipliers: **Comprehension check** before acknowledgement, and **Handover pack download**.
**Decision gate: Sun 22:00 IST.** Start bonus work only if R3-1 to R3-4 are merged, tested and working on the live site. Otherwise skip it. List bonus features separately from the three promised improvements.

### Stretch (only after everything above is tested)
- **R3-6 Per-visitor workspace** (a real Round 2 weakness): each browser session gets its own copy of the seeded demo project, so judges do not see each other's approvals. Concept: key every query by a `project_id` that is created per session.
- **R3-7 Continuation plan:** a simple Day 1 / Week 1 / Month 1 view built by rules from approved claims (blockers and risks -> Day 1, next actions -> Week 1, open questions and dependencies -> Month 1). Not promised; only if time remains.

---

## 6. Data model changes (additive migrations; the bootstrap must stay idempotent)
- `claim_versions(id, claim_id, version, text, editor_id, reason, created_at)`
- `claim_slots(claim_id, subject, attribute, value, normalized_value)` (or columns on `claims`)
- `gaps(id, project_id, gap_type, subject, related_claim_id, status, created_at)`
- `questions(id, gap_id, text, status, assigned_role, created_by, created_at)` and `answers(id, question_id, text, author_id, source_id, created_at)`
- `sources.source_type` gains `interview`
- `handover_versions(id, project_id, version, released_by, released_at, snapshot_json)`
- `handover_acks(id, handover_version_id, user_id, acknowledged_at)`
- New role value `departing`

---

## 7. Quality gates (do not skip)

1. **Tests first for the trust rules.** Every improvement ships with pytest tests (temporary database, fake provider, no real API calls).
2. **No real provider calls in tests.** Limit real calls on the live site; always keep the cached fallback.
3. **Each improvement is "done" only when:** code merged on `main`, tests pass, it works on the **live Streamlit site** in an incognito window, and it appears in `TESTING.md`.
4. **Commit small and often** with clear messages (it is your evidence of work inside the window).
5. **Feature freeze Mon 12:00.** After that: bugs, docs, PDF only.
6. **Never leave `main` broken.** Work on a branch per improvement, merge when green. Streamlit Cloud redeploys from `main`.
7. **Redeploys reset the demo database.** Do your final live check AFTER the last push.

---

## 8. Agent prompts (RUN ONLY AFTER 23:59 IST FRI 13 NOV)

Common header for every prompt:
```
Context: Round 3 of CodersInPune; window 23:59 IST Fri 13 Nov to 23:59 IST
Mon 16 Nov 2026. Read ROUND3_MASTER_PLAN.md, AGENT_QA_BRIEF.md and
AGENT_QA_BRIEF_DEPLOYED.md. Rules: work on a new branch; small commits; never
rewrite history; never print secrets; synthetic data only; no real provider
calls in tests; explain every new tool/library/concept in plain words (how and
why); keep QA_SESSION_LOG.md updated; additive, idempotent migrations only;
stop at the end and show me a summary of changes, tests run, and how to try the
feature in the UI. Do not push; tell me when ready.
```

**R3-0 Setup**
```
[header] Task R3-0: create branch r3/setup; run the full existing pytest suite and
report; add the migration scaffolding described in section 6 as empty,
idempotent bootstrap steps only (no feature behaviour yet); add a
`docs/ROUND3_LOG.md` listing the window times and the Round 2 tag
`round2-submitted`. Confirm the app still starts from an empty database.
```

**R3-1 Provider-safe extraction**
```
[header] Task R3-1 (section 5, R3-1): create ONE choke-point module for all
provider requests. Only public-sensitivity chunks may be included; a restricted
chunk reaching it raises an error. Add a masking module (emails, phones,
key-like tokens, ID-number-like digit runs) used before every provider call and
at read time for Incoming. Route Gemini and OpenRouter calls only through the
choke point. Restricted sources get local heuristic extraction only. Show
"masked values" counts and the extraction method in the Review UI. Write pytest
tests with a fake provider that captures payloads (assert the fake secret and
fake phone never appear; restricted chunk raises; masking table; fallbacks).
Update DISCLOSURES.md and ARCHITECTURE.md honestly.
```

**R3-2 Conflict and missing-evidence detection**
```
[header] Task R3-2 (section 5, R3-2): add claim slots (subject, attribute,
value) with rule-based extraction and optional cached LLM extraction through the
R3-1 choke point; deterministic conflict comparison with normalisation (names,
dates); statuses Conflicting / Possible conflict / Corroborated (sources
AGREE); missing-evidence gap rules (task without owner, decision without
date/rationale, risk without mitigation, single-source claims). Add a Conflicts
and Gaps panel with side-by-side versions and citations and a resolution action
that is audited. Add synthetic demo sources with 2-3 deliberate conflicts and
several gaps. Add pytest tests listed in the plan. Update the validator wording.
```

**R3-3 Exit interview**
```
[header] Task R3-3 (section 5, R3-3): add the Departing role and an Exit
Interview page: generate questions from open gaps (templates, optional cached
LLM wording via the choke point), let Reviewer edit/add/delete and send; Departing
sees only their assigned questions and submits answers; answers become a new
`interview` source with author/timestamp/sensitivity, chunked, then claims are
extracted from that source only and added as PENDING. Track gap status
(open / answered-pending-review / resolved). Add tests and demo data.
```

**R3-4 Editing and versions**
```
[header] Task R3-4 (section 5, R3-4): claim editing with append-only
claim_versions, edit reason, History expander; editing an approved claim makes
it Pending; audit rows. Tests per the plan.
```

**R3-5 Release and acknowledgement**
```
[header] Task R3-5 (section 5, R3-5): Release handover (snapshot in
handover_versions), Incoming sees the latest release, Acknowledge button
(handover_acks), snapshot immutability tests, role checks, UI status text.
```

**R3-QA Live QA and docs (Mon 12:00 onward)**
```
[header] Task R3-QA: run Phase D from AGENT_QA_BRIEF_DEPLOYED.md on the live URL
(Playwright if available), judge-journey for all new features, then update
README.md, ARCHITECTURE.md, TESTING.md, KNOWN_LIMITATIONS.md, CHANGES_FROM_PLAN.md,
DISCLOSURES.md, and write ROUND3_DELIVERED.md listing, for each of the three
improvements, what was delivered, where to see it in the UI, which tests prove it,
and what is NOT done. Be honest about gaps.
```

---

## 9. Final deliverables checklist
- [ ] Live link works in incognito (public app, correct main file, secrets set)
- [ ] Repo public; README has live URL, setup steps, roles, limits
- [ ] Three improvements each demonstrable in the live UI in under 2 minutes
- [ ] Tests pass; `TESTING.md` lists journeys, failure cases, permissions, reliability notes
- [ ] Privacy, security, accessibility and responsible-design explanation in the PDF
- [ ] Known limitations and roadmap are honest
- [ ] Updated project PDF uploaded to Drive (Anyone with link, Viewer), tested in incognito
- [ ] Improvements-completed list, technical details, contributions written
- [ ] AI disclosure updated (Gemini, Copilot, Claude, in-product models)
- [ ] Your own entry filed (role + what you built, in your words)
- [ ] Submitted at least 5 hours before 23:59 Mon 16 Nov

---

## 10. Risk register
| Risk | Mitigation |
|---|---|
| Improvement 3 is a big bundle | Build in order: R3-1, R3-4, R3-5. Each is independently demonstrable |
| Free API quota exhausted | Cached outputs, rule-based fallbacks, deterministic comparison code |
| Breaking the live app near the deadline | Feature freeze Mon 12:00; branches; merge only when tests pass |
| Redeploy resets demo data | Seed data is automatic; do the last check after the last push |
| Sleep debt | Plan sleep; stretch items are optional |
| Judges meet an app asleep | Open it shortly before submitting; mention hibernation in docs |
