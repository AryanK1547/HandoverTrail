# Round 3 Improvements Delivered

This note separates local implementation/test evidence from behavior actually
observed on Streamlit Community Cloud. The deployed QA run on 13 Nov 2026 made
no user-initiated write actions and did not call a provider, but rendering
Review Claims automatically recalculated and persisted derived conflict/gap
records. The run did not approve claims, upload data, create a release, or
acknowledge one.

## 1. Conflict and missing-evidence detection

**Delivered:** Rule-based claim slots and normalized comparisons distinguish
conflicting values, possible conflicts, and agreeing values. Gap rules cover
unowned tasks, incomplete decisions, risks without mitigations, and
single-source claims. The Reviewer can inspect side-by-side versions and
evidence citations; resolutions write audit records. Synthetic demo sources
provide deliberate owner/date/policy disagreements and evidence gaps.

**Where in the UI:** Open **Review Claims** → **Conflicts and gaps**. The live
Reviewer view displayed three Version A/Version B comparisons, citations, and
resolution controls. The QA run did not activate a resolution.

**Tests:** In [`tests/test_backend.py`](./tests/test_backend.py):
`test_conflict_detector_flags_disagreeing_owners`,
`test_conflict_detector_normalizes_names_and_dates`,
`test_similar_subject_mismatch_is_labelled_possible_conflict`,
`test_gap_detector_covers_missing_owner_date_rationale_mitigation_and_single_source`,
and `test_conflict_resolution_is_audited`. The complete local suite passed
**36 tests**.

**Not done / limits:** Live conflict resolution was not saved; live resolution
auditing was therefore not checked. Rules recognize supported wording only,
and matching/corroboration does not establish truth or source independence.
The Incoming role sees no gaps because it cannot read unapproved claims.

## 2. Gap-to-question exit interview

**Delivered:** Reviewers can generate local template questions from open gaps,
add/edit/delete drafts, and send them to the demo Departing identity. Departing
can answer only assigned questions. An answer is recorded with author,
timestamp, and sensitivity as an `interview` source; local extraction creates
pending claims, and approving a linked claim resolves its gap.

**Where in the UI:** Open **Exit Interview** as Reviewer to prepare questions;
select **Departing** to see assigned questions and answer forms. In the live
check (with no user-initiated writes) the Reviewer controls were visible, while
Departing saw an empty assigned-question state.

**Tests:** In [`tests/test_backend.py`](./tests/test_backend.py):
`test_exit_interview_questions_are_generated_editable_and_role_scoped` and
`test_exit_interview_answer_becomes_scoped_pending_evidence_and_resolves_gap`.
These use an isolated database and fake/no provider calls. The complete local
suite passed **36 tests**.

**Not done / limits:** Live question generation, send, answer submission,
interview-source persistence, and approval-to-gap-resolution were not
performed. Question wording uses deterministic templates; optional LLM
rewording was not implemented. The Departing identity is simulated, not
authenticated.

## 3. Provider-safe, accountable handover

**Delivered:** Gemini and OpenRouter requests pass through one provider
gateway. Only public evidence is eligible for external calls; common contact,
credential-like, and long numeric patterns are masked. Restricted evidence
uses local heuristic extraction. Claim edits append history and return claims
to pending review. Admin/Reviewer releases immutable snapshots containing
approved claims with public evidence; Incoming can acknowledge a specific
release version.

**Where in the UI:** **Review Claims** contains extraction, claim edit forms,
and **History** expanders. **Handover View** contains release controls and,
for Incoming, the released snapshot and acknowledgement action. The live UI
showed the Reviewer controls, but no release existed; Incoming therefore saw
“No handover has been released yet.”

**Tests:** In [`tests/test_backend.py`](./tests/test_backend.py):
`test_mask_sensitive_text_redacts_contacts_credentials_and_ids`,
`test_mask_sensitive_text_preserves_ordinary_text`,
`test_provider_gateway_masks_payload_and_rejects_restricted_chunks`,
`test_extraction_sends_only_public_chunks_and_uses_local_restricted_heuristic`,
`test_provider_failure_uses_labeled_local_fallback`,
`test_claim_edits_append_history_and_revoke_approved_incoming_visibility`,
`test_claim_edits_require_reviewer_and_a_reason`,
`test_handover_release_snapshot_is_immutable_and_public_only`, and
`test_handover_release_versions_acknowledgement_and_role_checks`. Tests use
synthetic values, isolated SQLite databases, and fake providers. The complete
local suite passed **36 tests**.

**Not done / limits:** No live extraction was run, so provider availability,
model selection, response quality, latency, and Cloud secret configuration
remain unverified. Live claim edits, release, and acknowledgement were not
performed. The initial Cloud state had no approved claims or release. The role
selector is not authentication, the Incoming Upload Sources page exposes
write controls, and local Cloud storage is not durable.

## Cross-cutting status

- Merged `main` and the live footer both identified `839953b`
  (`839953ba1c7a79f3d31e99601fe5db7ebeb6c5b5`).
- Local suite: **36 passed**; no real provider requests.
- The complete Cloud judge journey was **not** completed. See
  [`DEPLOYED_QA_REPORT.md`](./DEPLOYED_QA_REPORT.md) for what was and was not
  verified.
- The Round 3 plan dates the opening at 23:59 IST on 13 Nov 2026, but the
  reachable Round 3 implementation/merge commits are timestamped 01:43–16:23
  IST that day. This QA run also occurred at about 16:47–16:55 IST, before
  that opening and the plan's Monday QA block. History was not rewritten. If
  those dates are enforced, the work and QA evidence may affect eligibility;
  confirm with the organizer.
