# ROUND 3 UI/UX REFINEMENT ADDENDUM
## HandoverTrail — Professionalism, User Orientation & Interaction Quality

**Purpose:** Refinement of `ROUND3_UI_DESIGN_SPEC.md`

**Status:** Planning only. No implementation changes before 23:59 IST, Friday, 13 November 2026.

---

## 1. Design philosophy

HandoverTrail must feel like a professional project-management and knowledge-management product, not a generic AI-generated dashboard.

The interface should communicate four things continuously:

1. **Where am I?** — Current workflow stage and page.
2. **What is happening?** — Current operation or system state.
3. **Why is this happening?** — Explanation of the state, decision or restriction.
4. **What should I do next?** — One clear and relevant next action.

### Core design principle

> HandoverTrail should never leave a user guessing. Every screen must communicate the current state, the reason behind that state, whether an action is required, and what the user can safely do next.

The product should feel calm, predictable, responsive and trustworthy.

## 2. Visual refinement

### 2.1 Overall aesthetic

Retain the existing dark design system and colour tokens.

Refine the visual language using these principles:

- Minimal, structured layouts.
- Clear visual hierarchy.
- Restrained use of accent colours.
- Consistent spacing and alignment.
- Subtle borders instead of excessive shadows.
- Compact but readable information.
- Consistent iconography.
- No unnecessary decorative elements.

Avoid:

- Excessive gradients and glowing effects.
- Glassmorphism used only for decoration.
- Animated backgrounds.
- Too many cards nested inside other cards.
- Large decorative statistics.
- Unnecessary charts and progress percentages.
- Emojis as a replacement for consistent interface icons.
- Repeated badges that communicate the same information.

### 2.2 Colour usage

Retain the existing semantic colour system.

Use colours consistently:

| Colour | Meaning |
|---|---|
| Indigo | Primary action, active navigation |
| Green | Approved, successful, completed |
| Amber | Pending, attention required |
| Red | Rejected, denied, failed |
| Orange | Conflicting information |
| Purple | Restricted information |
| Blue | Public information |
| Neutral | General content and secondary information |

Never use colour as the only way to communicate a status. Every status must have readable text and, where appropriate, an icon.

### 2.3 Visual hierarchy

Each page should have:

1. Page title.
2. One-line explanation of the page's purpose.
3. Current role indicator.
4. Relevant next-step guidance.
5. Main content.
6. Secondary details and advanced information.

Avoid giving every section equal visual importance.

The primary action should be visually obvious without making every other button look equally important.

## 3. Progressive disclosure — reduce information overload

Introduce progressive disclosure throughout the application.

The user should see essential information first and access detailed information when needed.

### Claim cards

The default collapsed view should contain:

- Claim statement.
- Claim type.
- Trust status.
- Review status.
- A short evidence count.
- Relevant actions.

Expanded details should contain:

- Supporting source names.
- Exact evidence excerpts.
- Source location or line reference.
- Evidence provenance.
- Extraction origin.
- Validation explanation.
- Review history, where available.

Do not display every detail simultaneously.

### Evidence presentation

Evidence should be easy to inspect and compare.

When multiple sources support a claim:

- Display each source separately.
- Preserve the original wording.
- Make the source name visible.
- Clearly distinguish direct evidence from system interpretation.
- Do not merge contradictory evidence into a single reassuring summary.

### Advanced details

Use expanders for:

- Extraction methodology.
- Trust-label explanation.
- Audit history.
- Technical metadata.

The default interface must remain understandable without opening every expander.

## 4. Trust, review and sensitivity must remain separate

These are three different dimensions and must never be visually or logically merged.

### Trust

Explains the evidence supporting a claim:

- Corroborated — only when agreement has actually been checked.
- Single source.
- Missing evidence.
- Conflicting.

**Important limitation:** If the current implementation only counts independent source files, do not use "Corroborated" to imply that those sources agree.

Until agreement checking exists, use an honest label such as:

`Multiple sources — agreement not checked`

### Review

Explains the human review state:

- Pending.
- Approved.
- Rejected.
- Edited — pending review.

Approval must not automatically strengthen evidence quality.

### Sensitivity

Explains who is permitted to access the source or information:

- Public.
- Restricted.

Do not allow a claim's visibility to exceed the permissions of its supporting evidence.

## 5. Interaction and feedback requirements

Every meaningful user action must produce clear feedback.

### 5.1 Uploading

During upload, communicate:

- Which file is being processed.
- Which files were accepted.
- Which files were rejected.
- Why a file was rejected.
- Whether the accepted files were successfully saved.

Never show a generic success message if only some files were accepted.

### 5.2 Extraction

Use truthful progress states.

Example:

1. Preparing permitted sources.
2. Checking source sensitivity.
3. Preparing evidence excerpts.
4. Running extraction.
5. Validating evidence references.
6. Saving candidate claims.

Only display stages that the implementation actually performs.

Do not invent completion percentages or estimated remaining time.

If extraction fails, communicate:

- What failed.
- Whether source data remains saved.
- Whether candidate claims were partially saved.
- Whether retrying is safe.
- What the user can do next.

### 5.3 Reviewing claims

After an action:

- Approve: confirm the database saved the approval.
- Reject: request confirmation before rejection and provide an optional reason.
- Edit: preserve changes and indicate that the edited claim needs review.
- Failure: retain the existing review state and show a useful error.

Do not display success before the underlying operation succeeds.

Prevent accidental duplicate submissions while an operation is in progress.

### 5.4 Releasing a handover

Before release, show a summary of:

- Approved claims included.
- Claims excluded.
- Restricted information excluded.
- Unresolved conflicts or evidence gaps.
- Intended recipient role.

Require confirmation before release.

After successful release, show the release status and timestamp.

## 6. Never leave the user at a dead end

Every page must have meaningful empty, loading, error and success states.

| Situation | Required communication |
|---|---|
| No sources | Explain that sources are needed and provide an upload/demo action |
| Upload failed | Explain the failure and provide a retry option |
| No claims found | Explain the extraction result and next available action |
| Extraction running | Show actual processing stages |
| Extraction failed | Explain what was saved and what can be retried |
| No pending reviews | Confirm that the review queue is clear |
| No approved claims | Explain that a handover cannot yet contain approved information |
| No conflicts detected | State that no conflicts were detected by the implemented checks |
| Conflicting claims | Display both sides and request human resolution |
| Missing evidence | Explain what information is missing |
| Incoming sees hidden information | Explain how many items were excluded and why |
| Database unavailable | Explain that the requested action could not be saved |

Never use empty screens without an explanation.

Never claim that no conflicts exist if conflict detection has not been implemented.

## 7. Preserve user work and application responsiveness

The application must remain predictable during slow operations and failures.

Required behaviours:

1. Disable relevant action buttons while their operation is running.
2. Preserve unsaved edits when possible.
3. Avoid silently clearing uploaded files after extraction errors.
4. Do not duplicate claims when a user retries an operation.
5. Clearly distinguish saved changes from unsaved changes.
6. Provide retry actions when retrying is safe.
7. Avoid unnecessary full-page resets.
8. Show database errors in understandable language without exposing secrets or internal credentials.

Where an operation cannot safely be retried, explain why.

## 8. Navigation and user orientation

Retain the five-stage workflow rail:

**Connect → Reconstruct → Verify → Review → Handover**

Every page must communicate:

- Current stage.
- Completed stages.
- Upcoming stages.
- Current role.
- Project context.
- One relevant next action.

Do not make unavailable or prerequisite-dependent steps appear ready for use.

The next-step banner must derive its message from actual application state.

Examples:

- "3 sources uploaded. Run reconstruction to generate candidate claims."
- "4 claims are awaiting review."
- "2 claims need additional evidence."
- "Nothing is approved yet. Review claims before preparing the handover."
- "The handover is ready for release."

These are examples only. Display them only when the underlying database state supports them.

## 9. Information density and page layout

Each page should have one primary purpose.

### Landing

Explain the product and provide one obvious way to begin.

### Connect

Focus on adding and inspecting project sources.

### Reconstruct

Focus on extraction method, processing progress and extraction results.

### Verify / Review

Focus on evidence inspection, trust labels and human decisions.

### Handover

Focus on the final approved information, role visibility and release.

Avoid combining upload controls, extraction controls, review queues and handover previews into one crowded screen.

## 10. Accessibility and interaction quality

Retain the original accessibility requirements and additionally verify:

- All interactive controls have understandable labels.
- Keyboard navigation works.
- Focus remains visible.
- Error messages are readable and actionable.
- Status changes are communicated with text.
- Buttons have sufficient clickable area.
- Content remains readable at 375px, 768px and 1440px.
- Reduced-motion preferences are respected.
- Long filenames and claim text do not break the layout.

Use subtle transitions only when they improve feedback. Motion must never delay an action or obstruct the user.

## 11. Implementation boundaries

This addendum refines presentation and interaction. It does not authorize changes to the core business logic.

Do not:

- Change the database schema solely for visual polish.
- Replace evidence-validation rules with visual indicators.
- Invent AI confidence or accuracy scores.
- Claim conflict detection before it exists.
- Add unnecessary dependencies.
- Introduce animations that compromise reliability.
- Expose restricted information through previews, summaries or notifications.
- Sacrifice existing tests to achieve a visual effect.

Preserve the original design specification's single centralized CSS approach and native Streamlit components wherever possible.

## 12. Additional acceptance checklist

### Visual quality
- [ ] The interface does not resemble an unmodified Streamlit application.
- [ ] Colour and typography remain consistent across pages.
- [ ] Primary actions are immediately recognizable.
- [ ] Cards are not unnecessarily nested or overloaded.
- [ ] Badges are used only where they add useful information.
- [ ] Expanded evidence is readable and well structured.

### User experience
- [ ] Every meaningful action gives feedback.
- [ ] No loading operation leaves the user staring at an unexplained spinner.
- [ ] Every empty state explains what happened and what to do next.
- [ ] Every failure explains whether data was saved.
- [ ] Duplicate submissions are prevented where appropriate.
- [ ] Unsaved review work is not silently discarded.
- [ ] The user can always identify their current role and workflow stage.

### Trust and safety
- [ ] Trust, review and sensitivity are displayed separately.
- [ ] Source agreement is never implied by source count alone.
- [ ] Conflicting evidence is not silently resolved.
- [ ] Restricted information is excluded before retrieval and AI processing for unauthorized roles.
- [ ] Handover release includes only permitted, approved information.
- [ ] Success messages appear only after successful persistence.

### Final quality
- [ ] Original tests still pass.
- [ ] New interaction states are tested.
- [ ] Desktop and mobile layouts are inspected.
- [ ] No fake metrics or unsupported product claims appear.
- [ ] No existing functionality is broken by the redesign.

---