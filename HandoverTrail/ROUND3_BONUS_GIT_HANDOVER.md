# ROUND 3 BONUS: "Git Handover" and two cheap multipliers

Addendum to `ROUND3_MASTER_PLAN.md`. Same rules apply: **no feature code, fixtures or migrations before 23:59 IST Fri 13 Nov 2026.**
Planning, design and prompts like these are allowed now.

## 0. Honest scoring logic (read this first)

- Round 3 is judged on: completeness (25), the **three promised improvements** (20), reliability (20), usability and real-world fit (20), documentation (15). There is **no "originality" line** in Round 3.
- So an extra feature wins points only through **real-world fit, completeness and the memorable demo**, and only if it **works reliably and plugs into the existing workflow**. A half-working bonus feature costs points under "reliability".
- Therefore the bonus must be: (1) deterministic (no AI guesswork, so it is testable), (2) free and offline-capable, (3) feeding the **same Claim Ledger** (so it is part of the product, not a side app), (4) listed in the final PDF as **"additional, beyond the three promised improvements"**, never as a replacement for them.
- **Decision gate:** start bonus work ONLY if, by **Sun 22:00 IST**, improvements R3-1, R3-2, R3-3 and R3-4 are merged on `main`, their tests pass, and they work on the live site. Otherwise skip the bonus entirely and spend the time on reliability and docs.

---

## 1. Flagship bonus: GIT HANDOVER ("Leaver Footprint")

### The idea in plain words
Most teams will summarise documents with an AI. Almost nobody will look at the **history of the code itself**, even though it records exactly who knows what. From a team's git history, HandoverTrail can compute, with plain code and no AI guessing:
- **who owns which part of the project** (share of commits per area),
- **where knowledge is concentrated in one person** (a "single point of knowledge", also called a *bus factor* of 1: if that one person is hit by a bus, or simply leaves, the knowledge goes with them),
- **what a specific leaving person alone knows**, their "footprint",
- **which parts are stale** and **which parts keep breaking** (recurring problems).

These become evidence-linked claims in the normal Claim Ledger (cited by commit hash and message), go through human review, respect roles, and feed the exit interview questions.

### Why it fits the brief
The brief explicitly lists repositories as a source and asks for ownership, dependencies, recurring problems and risks. This produces them from real, verifiable evidence, and it works for exactly the student and volunteer teams we chose.

### Input (robust, free, offline)
A text file the user creates with one command, run inside their repo:
- Windows PowerShell or any shell:
  `git log --pretty=format:"@@%H|%an|%ad|%s" --date=short --name-only > git_history.txt`
- **Concept: git log** prints the history of commits. `--pretty=format:` lets us choose the fields (`%H` commit hash, `%an` author name, `%ad` date, `%s` subject). `--name-only` lists the files changed in each commit. `@@` is a marker we add so the parser can split commits reliably.
- **We deliberately do NOT export emails** (`%ae`). Names are enough, and emails are personal data.
- Optional later (stretch): fetch a **public** repo through GitHub's REST API with a read-only token in secrets. Not needed for the demo, and rate limits make it risky. Keep the file mode as the primary path.

### What the code computes (all deterministic)
Concepts: a **parser** turns raw text into structured rows; **pandas `groupby`** counts rows per group; a **threshold** is a cut-off number that turns a count into a finding.
1. **Parse** into rows: commit hash, author, date, subject, file path (one row per file per commit). Handle merge commits, empty commits, unicode names, renames and missing file lists safely.
2. **Areas:** group files by top-level folder (or first two path segments), configurable.
3. **Ownership table:** per area, commits per author, top author share, last commit date.
4. **Single point of knowledge:** area or file where one author has at least 80% of commits AND at least 5 commits (thresholds visible and editable in the UI).
5. **Leaver footprint** (user picks the leaving person):
   - areas where they are the top owner,
   - areas where **only they** committed,
   - areas where they own most and nobody else committed in the last 90 days (highest risk),
   - their last active date and their last 10 commit subjects (cited).
6. **Stale areas:** no commits in the last 60 days. **Hot areas:** many commits in the last 14 days.
7. **Recurring problems:** a file or area with at least 3 commits whose subject contains words like fix, bug, hotfix, revert, workaround, hack, temp, wip (list is editable). This maps to the brief's "recurring problems".
8. **Every finding becomes a claim** with `claim_source = git_analysis`, a claim type (owner, risk, or blocker), and evidence chunks created from the actual commit lines (hash + date + subject + file), so the citation shows real commits.

### Trust and privacy design (this is also a scoring point under "responsible design")
- Output is framed as **knowledge at risk**, never as a productivity score. Do not rank people. Do not show commit counts as "performance". The page says: "This is for knowledge transfer, not for evaluating people."
- Contributor names are personal data: demo uses **synthetic** history (invented names), source defaults to **restricted**, and the uploader can mark it public. Incoming sees only approved claims whose sources are public, as always.
- Pass any text through the R3-1 **masking** module and the provider **choke point**. Findings are computed locally; no provider call is needed at all for this feature.
- Label in the UI: "Computed from git history (deterministic, no AI)".

### UI
New page **Git Handover**: upload the file, see a parsed summary (number of commits, authors, date range), an ownership bar chart (Streamlit built-in `st.bar_chart` with pandas), a "Knowledge at risk" table with severity, a **Leaver selector**, a footprint panel, and a **Generate claims** button that adds pending claims to the review queue. Findings that are gaps (for example, a risky area with no documentation source) feed the **exit interview** as questions ("You are the only committer of payments/. Where is the on-call or deployment knowledge for it?").

### Acceptance tests (pytest, no network, no AI)
- Parser: normal log, merge commit, empty commit, unicode name, no `--name-only` section, Windows line endings, empty file, garbage file (friendly error).
- Ownership shares sum correctly; top-author thresholds trigger and do not trigger as expected.
- Footprint for a chosen leaver on a synthetic log with known answers (exact expected lists).
- Staleness and hot-area cut-offs use a fixed "today" parameter (so tests never depend on the real date).
- Recurring-problem keyword rule.
- Generated claims have evidence chunks containing the real commit hashes; claims arrive PENDING; Incoming cannot see them if the source is restricted.
- No email-like strings appear in any output.
- Same input gives identical output (deterministic).

### Effort and cut rules
About 5 to 6 hours with the agent. If time is short: ship parser + ownership + single-point-of-knowledge + leaver footprint + claims. Cut recurring problems and hot areas first. Never ship it half-working: if not finished by Mon 10:00 IST, leave the page out of the live app (keep code on a branch) and do not list it.

---

## 2. Multiplier A: "Comprehension check" before acknowledgement (about 2 to 3 hours)

**Idea:** today "acknowledge" would be a click. Make it **proof of understanding**. When Incoming opens a released handover version, the app builds 5 multiple-choice questions from the approved claims ("Who owns X?", "What is the top risk?", "What is blocked?", "Which source disagrees about Y?"). Distractors come from other claims' values. Pass mark 60%. The acknowledgement records the version and the score ("acknowledged v2, understanding 4/5"), and shows which topics were missed so the reviewer can follow up.
- Deterministic generation (templates over claim slots from R3-2), no AI needed, so it is testable and cannot hallucinate.
- Fits the brief: "incoming person understands ownership, risks and next steps" is literally a success criterion, and this measures it.
- Depends on R3-2 (slots) and R3-5 (release + acknowledgement). Build after R3-5, and only if the decision gate passed.
- Tests: question generation from a fixed claim set; distractors never equal the right answer; score computed correctly; result stored with the acknowledgement; Departing/Reviewer cannot submit an Incoming acknowledgement.

## 3. Multiplier B: Download the handover pack (about 1 hour)

**Idea:** a button on the released handover that downloads a Markdown file ("handover pack"): version, date, released by, approved claims grouped by type, each with its citations, plus the list of unresolved conflicts and gaps. Streamlit's built-in `st.download_button` does this with no extra library.
- Real-world fit: the handover leaves the app and can live in the team's repo or drive.
- Respects roles: the file contains only what the viewing role may see (generated through the same retrieval layer), with masking applied.
- Tests: Incoming's pack contains no restricted text; pack contents match the released snapshot; filename includes the version.

---

## 4. Order of work with the decision gate

1. Promised work first, in the order of the master plan.
2. **Gate at Sun 22:00 IST** (see section 0).
3. If the gate passes: Git Handover (Sun night to Mon morning), then Comprehension check, then the pack download.
4. **Feature freeze Mon 12:00 IST** still applies to everything.
5. Update the PDF, README and TESTING.md only for what is live and tested. List these as **"Additional features beyond the three promised improvements"**.

---

## 5. Agent prompts (RUN ONLY AFTER 23:59 IST FRI 13 NOV, AND ONLY AFTER THE GATE)

Use the same header as in `ROUND3_MASTER_PLAN.md` section 8.

**G1 Git Handover**
```
[header] Task G1 (ROUND3_BONUS_GIT_HANDOVER.md section 1): add a Git Handover
page. Parse a `git log` export made with
git log --pretty=format:"@@%H|%an|%ad|%s" --date=short --name-only
(no emails). Implement deterministic analysis: areas, ownership shares,
single-point-of-knowledge thresholds (80% and 5 commits, adjustable), leaver
footprint, stale/hot areas with a fixed `today` parameter, recurring-problem
keywords. Show an ownership bar chart (st.bar_chart + pandas), a risk table, a
leaver selector and a Generate claims button that creates PENDING claims with
claim_source=git_analysis and evidence chunks built from real commit lines.
Default source sensitivity restricted. Pass output through the masking module.
Add the "knowledge transfer, not performance evaluation" notice and the
"computed, no AI" label. Create a synthetic git log fixture with invented names
and known expected answers. Add all tests listed in section 1. Explain pandas
groupby and the parsing approach to me in plain words.
```

**G2 Comprehension check**
```
[header] Task G2 (section 2): after the release/acknowledgement feature, add a
deterministic 5-question comprehension check for Incoming built from approved
claims and their slots; distractors from other claims; 60% pass mark; store the
score with the acknowledgement and show missed topics to the Reviewer. Add the
tests listed in section 2.
```

**G3 Handover pack download**
```
[header] Task G3 (section 3): add a role-aware Markdown "handover pack" download
on the released handover using st.download_button, generated only through the
role-filtered retrieval layer with masking. Add the tests listed in section 3.
```

---

## 6. How to describe it in the final submission
- In the **improvements-completed list:** the three promised improvements first, each with proof (UI location + tests).
- Then a separate heading **"Additional features beyond the three promised improvements"** with Git Handover (and the others only if live and tested).
- In the **PDF**, add one honest paragraph on privacy and responsible design for the git feature (names are personal data; synthetic demo; no emails; not for performance review).
- If a bonus feature is not finished, **do not list it as working.** Put it under "Known limitations / roadmap".
