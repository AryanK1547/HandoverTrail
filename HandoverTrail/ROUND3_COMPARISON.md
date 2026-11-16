# Round 2 → Round 3: promised, planned, delivered

Compares four things: the **Round 2 submission** (git tag `round2-submitted`,
commit `87b7c2b`), the **three improvements promised for Round 3**, the
**Round 3 master plan** (`ROUND3_MASTER_PLAN.md`), and what the repository
contains now. The final work was merged into `main` as `106d76e` and the live
site reported that commit on 16 Nov 2026. Earlier deployed findings
(`DEPLOYED_QA_REPORT.md`) describe commit `839953b`.

## 1. Where Round 2 stood

| Area | Round 2 behaviour (from the tagged README and limitations) |
|---|---|
| Sources | `.txt` and `.csv` upload or packaged demo; parsed into excerpts |
| Extraction | Gemini, then OpenRouter, then a labeled local heuristic |
| Review | Approve or reject claims as Admin or Reviewer |
| Incoming | Sees approved claims whose linked sources are all public |
| Sensitivity | Filtered **when displayed only**; restricted text could still be sent to a provider |
| “Corroborated” | Meant only “two or more files linked”; agreement was never checked |
| Conflicts, gaps | Not implemented |
| Editing, history, release, acknowledgement | Not implemented |
| Exit interview, masking | Not implemented |
| Workspace | One shared demo project; uploads mixed with demo data |

## 2. The three promised improvements

| # | Promise (Round 2 wording) | Master plan task | Delivered |
|---|---|---|---|
| 1 | Compare claims across sources for incompatible owners, dates, decisions; separate conflict from corroboration; flag missing owners, dates, decisions; show both versions side by side with citations | R3-2 | **Yes, rule-based.** Slot comparison with name and date normalization; Conflicting / Possible conflict / Corroborated; gap rules for task without owner, decision without date or rationale, risk without mitigation, single-source claim; Version A / B with citations; audited resolution; three deliberate conflicts in the synthetic data |
| 2 | Turn gaps into a short, editable question list for the departing person; answers saved as new evidence with owner and timestamp; normal review | R3-3 | **Yes.** Departing role; template questions per gap; reviewer edits, adds, deletes, sends; Departing sees only assigned questions; answer stored as an `interview` source with author, timestamp, and sensitivity; becomes pending claims; gap moves open → answered-pending-review → resolved on approval |
| 3 | Role-scoped extraction so restricted excerpts never reach a provider; masking before any model call; version history for approved handovers; acknowledgement recording which version Incoming received (plus claim editing, per the Round 2 PDF) | R3-1, R3-4, R3-5 | **Yes.** One provider gateway that raises if a restricted chunk reaches it; masking of emails, phones, key-like tokens, long IDs before provider calls and at read time for Incoming; append-only claim edit history, edit returns a claim to pending; immutable release snapshots (SQLite triggers reject update and delete); acknowledgement stored per version |

## 3. Master plan versus delivery

| Master plan item | Status | Note |
|---|---|---|
| R3-0 schema scaffold, `round2-submitted` tag | Done | Additive, idempotent migrations; tag exists |
| R3-1 provider-safe extraction, masking | Done | Tested with a fake provider that captures payloads |
| R3-UI design system | Done | Shared tokens, workflow rail, badges, contrast tests |
| R3-2 conflicts and gaps | Done | **Deviation:** the plan allowed cached LLM slot extraction; only rule-based extraction exists, so unusual wording is missed |
| R3-3 exit interview | Done | **Deviation:** optional LLM rewording of questions not built; templates only |
| R3-4 editing, version history | Done | |
| R3-5 release, acknowledgement | Done | Re-acknowledging is blocked; a newer release needs a new acknowledgement |
| Stretch R3-6 per-visitor workspace | **Done, beyond the plan's wording** | Upload workspaces by URL token, plus a one-click **private demo copy** so judges never inherit another visitor's approvals |
| Stretch R3-7 Day 1 / Week 1 / Month 1 plan | **Done** | “Where to pick up”: fixed rules from claim type (blockers and risks, then queued work and owners, then open questions and dependencies), each step cited |
| Bonus: Git Handover | **Not built** | Decision gate was Sun 22:00; no code exists |
| Bonus: comprehension check before acknowledgement | **Not built** | |
| Bonus: handover pack download | **Partly** | Released version downloads as Markdown; not a multi-file pack |
| Live QA on the deployed site | **Done on `106d76e`** | Scripted Chromium run of the full journey on the live site, 16 Nov 2026 (see README, Status of the live site) |
| Final PDF, own entry, submission form | **Open** | Outside the repository |

## 4. Changes beyond the plan

Found by driving the whole journey in a browser and by reviewing the pages:

- **Workspace isolation.** Uploads no longer mix with demo claims; each upload
  workspace is separate and survives refresh and navigation.
- **Role safety in the UI.** Incoming cannot see upload or review controls;
  Departing opening the handover page gets guidance instead of an error.
- **Guided flow.** Role-aware sidebar, a next-step banner computed from stored
  state, back/next links on every page, and an optional-interview rule so open
  gaps never hide the release action.
- **Review page.** Three stages (Reconstruct, Verify, Review); claim cards with
  the claim, a plain-language trust reason, and the quoted evidence inline;
  views for needs review, needs attention, approved, rejected.
- **Verification that means something.** A report of corroborated,
  single-source, conflicting, and missing-evidence counts plus a lexical
  evidence-match check (flags claims their own citation does not support).
- **Release safety.** Summary of included and excluded claims and a
  confirmation step; no duplicate versions when nothing changed.
- **Reliability fixes.** Interview question text no longer becomes a claim;
  claims are validated automatically after extraction and after an interview
  answer; the “latest extraction run” tie-break is deterministic; the upload
  limit text matches the real 2 MB limit.
- **Judge guidance.** A guided tour page with ten steps, each opening the right
  page as the right role, with completion read from stored data.

## 5. What a judge can verify, and what remains unproven

| Claim | Where to see it | Proof |
|---|---|---|
| Whole workflow works end to end | Guided tour, steps 1–10 | `test_guided_tour_follows_the_real_state_to_the_final_acknowledgement`; browser journey `full-journey.spec.ts` |
| Restricted data never reaches Incoming or a provider | Tour “Checks worth making”; Incoming source list | provider-gateway and visibility tests in `tests/test_backend.py` |
| Released versions cannot change | Release a version, then edit a claim | immutability test |
| Private copies are isolated | Start two copies | `test_private_demo_copies_are_complete_and_isolated` |

Local results: **57 backend tests and 5 browser journeys pass**, with provider
calls disabled in all of them.

Live site (`106d76e`, 16 Nov 2026): the full guided journey completed in a
scripted Chromium run, ending at 9 of 9 tour steps.

**Not verified:** live Gemini or OpenRouter responses (extraction was not run
on the live site), uploading your own files on the live site, Firefox and
WebKit, keyboard-only and screen-reader use, simultaneous users, and
persistence across a Streamlit Cloud restart (private copies live in the same
non-durable local SQLite file).

## 6. Before submitting

1. After any further push to `main`, wait for Streamlit Cloud to redeploy and
   re-check the footer commit; a redeploy resets the demo database.
2. Open the live URL in a private window and complete the guided tour once.
3. Confirm the schedule question in `CHANGES_FROM_PLAN.md`: the first Round 3
   commits are timestamped before the stated 23:59 IST window opening.
   History was not rewritten.
4. Update the project PDF, improvements list, AI disclosure, and your own entry;
   none of these live in the repository.
