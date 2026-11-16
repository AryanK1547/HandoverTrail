# ROUND 3 UI/UX DESIGN SPEC: HandoverTrail

Addendum to `ROUND3_MASTER_PLAN.md`.

## 0. Goals
1. **Professional and sleek:** a consistent design system, not default Streamlit.
2. **Keeps the user rooted at every step:** at any moment the user knows *where they are, who they are (role), what just happened, and what to do next.*
3. **Trust is visible:** public vs restricted, AI vs computed vs human-approved, and uncertainty are shown with consistent labels (never colour alone).
4. **Reliable first:** styling must never break the workflow. Small, testable, version-pinned CSS.
5. **Honest:** only real numbers are shown. No invented metrics (for example, never show a made-up "accuracy 94%").

---

## 1. Review of the pasted suggestions

| Suggestion | Verdict | Why |
|---|---|---|
| Dark theme in `.streamlit/config.toml` (indigo accent, slate background) | **Keep, refine** | Good base. Add `base = "dark"`, set semantic colours, check contrast. Merge with the existing `config.toml`; do not overwrite it blindly. |
| Inject CSS via `st.markdown(..., unsafe_allow_html=True)` | **Keep, but small and centralised** | Put it in ONE function (`apply_theme()`), not repeated per page. Target stable `data-testid` selectors. |
| `.stApp` background override | **Drop** | The theme already sets it; hard-coding fights the theme. |
| `div.stMarkdown, div.stMetric` card styling | **Reject** | Would put a box around every paragraph and break layouts. Use native `st.container(border=True)` for cards instead. |
| Button restyle | **Keep, minor** | Let the theme's `primaryColor` do most of it; small CSS for radius, weight, focus ring. |
| Hide menu and footer via CSS | **Replace** | Use `[client] toolbarMode = "minimal"` in config, and a small footer of our own. Do not hide the whole header (it holds the sidebar toggle). |
| `st.metric(label="Extraction Accuracy", value="94%")` | **Reject** | It is a fabricated number. It would contradict the product's core rule (no unsupported claims). Show real counts only. |
| Columns and metrics | **Keep, with real data** | Sources, excerpts, claims by status, open conflicts, open gaps. |
| Status banners / badges for public vs restricted | **Keep and extend** | Consistent badge set with icon + text. |
| Sidebar navigation with section dividers | **Keep, improve** | Add a workflow rail (below) so the order of steps is clear. |

---

## 2. Design system (design tokens)

**Concept: design tokens** are named values (colours, spacing, radius) defined once and reused, so the whole app looks consistent and can be changed in one place.

### Colours (dark theme)
| Token | Value | Use |
|---|---|---|
| bg | `#0B1220` | page background |
| surface | `#111B2E` | cards, sidebar |
| surface-2 | `#18243B` | hover, nested panels |
| border | `#27344D` | card borders |
| text | `#E6EBF5` | main text |
| text-muted | `#9AA7BF` | secondary text |
| primary | `#6366F1` | buttons, active step |
| primary-text | `#A5B4FC` | links, active labels on dark |
| success | `#34D399` | approved, corroborated |
| warning | `#FBBF24` | single source, pending |
| danger | `#F87171` | missing evidence, rejected, denied |
| conflict | `#FB923C` | conflicting |
| restricted | `#C4B5FD` | restricted source badge |
| public | `#7DD3FC` | public source badge |

**Contrast rule:** normal text must reach a **WCAG contrast ratio of 4.5:1** (a measure of readability between text and background colour). The agent computes the ratios for every text/background pair in a small script and fixes any pair below 4.5:1 (3:1 for large text).

### Typography and spacing
- Font: Inter (loaded by CSS `@import`), with a system sans-serif fallback so nothing breaks if the font is blocked.
- Sizes: body at least 15px, secondary text at least 13px. Clear heading hierarchy (page title, section title, caption).
- 8px spacing grid. Max content width about 1200px (`layout="wide"` with sensible padding). Radius 10px on cards, 8px on buttons.

### Icons
Use Streamlit's Material icon syntax (for example `:material/inventory_2:`) instead of emoji, for a consistent professional look. The agent must confirm the syntax is supported by the pinned Streamlit version (1.67.0).

### Badges (always icon + text, never colour alone)
| Badge | Text |
|---|---|
| Source sensitivity | `Public`, `Restricted` |
| Trust | `Corroborated (2+ files)`, `Single source`, `Missing evidence`, `Conflicting` |
| Review | `Pending`, `Approved`, `Rejected` |
| Origin | `AI-extracted`, `Computed (no AI)`, `Human-edited`, `Cached demo` |
| Role | `Admin`, `Reviewer`, `Incoming`, `Departing` |

---

## 3. "Keep the user rooted": the orientation system

These five elements appear on every page. Together they answer "Where am I? Who am I? What happened? What next?"

1. **Workflow rail** (top of every page): `Connect > Reconstruct > Verify > Review > Handover`. Each step shows a state (done / current / upcoming) and a real count (for example "Review: 4 pending"). Built with `st.columns` + `st.page_link` so steps are clickable, with the current step highlighted. On a phone it collapses to "Step 4 of 5: Review".
2. **Page header:** page title, one-line purpose ("Approve or reject each claim. Every claim shows its evidence."), and the current role badge.
3. **Next-step banner:** computed from the database, never hard-coded. Examples: "4 claims are waiting for review. Go to Review", "Nothing approved yet. Approve a claim to build the handover", "2 conflicts need a decision". One clear primary action per page.
4. **Sidebar identity block:** project name, **role selector with a one-line description of what that role can do**, data mode (`Synthetic demo data`), AI mode (`Cached` / `Live: Gemini` / `Local fallback`).
5. **Feedback after every action:** toast messages ("Claim approved. It is now visible to Incoming"), confirmation dialog for rejecting or releasing, and `st.status` progress during extraction that shows the *true* steps ("Masking sensitive values", "Sending 14 public excerpts", "Validating evidence links"). This also makes the safety story visible to judges.

Also required:
- **Empty states** that teach: icon + one sentence + the action button ("No sources yet. Load the demo project").
- **Glossary popover** (`st.popover`) on pages with labels: what Corroborated, Single source, Missing evidence, Conflicting, Public, Restricted mean.
- **Why hidden?** For Incoming, a plain sentence: "3 items are hidden because they rely on sources you are not authorised to read."
- **Footer:** app version (git short hash), "Synthetic demo data only", link to the README/limitations.

---

## 4. Page-by-page layout

| Page | Layout |
|---|---|
| **Landing** | Hero: name, one-line promise, "Load demo project" primary button. Below: the five-step workflow as five cards with icons and one line each. A "Try it in 2 minutes" numbered path. Trust strip: "Every claim cites its source. Restricted sources stay hidden. Humans approve." |
| **Connect (Upload Sources)** | Stat row (sources, public, restricted, excerpts). Tabs: `Load demo`, `Upload files`, `Git history` (when built). Source table with sensitivity badges. |
| **Reconstruct (Extraction)** | Method selector with explanation; run button; `st.status` progress; summary of claims created, masked values count, method used. |
| **Verify / Review** | Filter pills (status, type, sensitivity). Each claim in a bordered card: claim text, type, trust badge, review badge, evidence in an expander with source names, actions (Approve / Reject / Edit when built) aligned right. Conflicts and gaps panel side-by-side when built. |
| **Handover** | Release header (version, date, released by), grouped sections by claim type, citations as expanders, hidden-count notice, acknowledgement and comprehension check when built, download pack button when built. |

---

## 5. Safety rules for the UI code (reliability and security)

1. **Escape dynamic text.** Badges and cards that use `unsafe_allow_html=True` must pass every dynamic value through `html.escape()`. Never put claim text, file names or user input into raw HTML unescaped (that would allow HTML or script injection). Test: a claim containing `<script>alert(1)</script>` renders as plain text.
2. **No new dependencies.** Only Streamlit features and plain CSS. Streamlit stays pinned at the current version; the agent re-runs the app after styling.
3. **One CSS block**, under about 150 lines, inside `ui.apply_theme()`. Prefer native components (`st.container(border=True)`, `st.tabs`, `st.status`, `st.popover`, `st.dialog`, `st.toast`) over CSS hacks. CSS selectors based on Streamlit internals can change between versions, which is why the version is pinned and the result is checked in the browser.
4. **Logic must not change.** The redesign is a presentation layer; all existing tests must still pass unchanged.
5. **Accessibility:** contrast checked, visible keyboard focus ring, status never shown by colour alone, respect `prefers-reduced-motion` (no animations beyond subtle transitions), readable sizes.
6. **Performance:** pages should not become slower; no large images; fonts are optional with a fallback.

---

## 6. Acceptance checklist
- [ ] Every page shows the workflow rail, header with role badge, and a computed next-step banner.
- [ ] Sidebar shows project, role (with description), data mode and AI mode.
- [ ] All badges use icon + text, and contrast ratios are 4.5:1 or better.
- [ ] Empty states exist for: no sources, no claims, nothing approved, nothing hidden, no conflicts.
- [ ] Approve, reject and release give a toast; reject and release ask for confirmation.
- [ ] Extraction shows a truthful `st.status` sequence.
- [ ] No invented numbers anywhere; every metric is computed from the database.
- [ ] Mobile (375px): no horizontal page scroll; rail collapses; buttons are tappable.
- [ ] A `<script>` test string is displayed as text everywhere.
- [ ] All existing pytest tests pass; live site works in incognito after deploy.
- [ ] Before/after screenshots saved at 375, 768 and 1440 px for the final PDF.

---

## 7. Time-box and cut rules
- Budget: **about 3.5 hours**, placed right after R3-1 and **before R3-2**, so every new page (conflicts, exit interview, release, git) is built on the design system instead of being restyled later.
- Cut order if over budget: animations, per-page polish, glossary popover, mobile rail collapse. **Never cut:** the workflow rail, role badge, next-step banner, badges, escaping, tests.
- Stop at 4 hours regardless. Reliability beats polish.

---

## 8. Agent prompt R3-UI (RUN ONLY AFTER 23:59 IST FRI 13 NOV)

Use the same header as in `ROUND3_MASTER_PLAN.md` section 8.

```
[header] Task R3-UI: implement ROUND3_UI_DESIGN_SPEC.md on a branch r3/ui. Steps:
U1 Run `git diff` on .streamlit/config.toml, then MERGE (do not overwrite):
   [theme] base="dark" plus the tokens in section 2, [client] toolbarMode =
   "minimal". Keep secrets.toml untouched and ignored.
U2 Create ui.py with: apply_theme() (one CSS block under ~150 lines, Inter with
   fallback, focus ring, radius, reduced-motion), page_shell(step, title,
   subtitle), workflow_rail(current_step) using st.columns + st.page_link with
   real counts from the database, next_step_banner() computed from DB state,
   sidebar_identity() (project, role selector with role description, data mode,
   AI mode), badge helpers (status, sensitivity, review, origin, role: icon +
   text, html.escape on all dynamic text), empty_state(), stat_row(), glossary
   popover, footer (git short hash if available, "Synthetic demo data only").
   Call st.set_page_config as the first Streamlit call on each page, via the helper.
U3 Restyle the landing page and the three existing pages using ONLY these
   helpers and native components (st.container(border=True), st.tabs,
   st.status, st.popover, st.dialog, st.toast). Do not change any business
   logic. Replace emoji with :material/...: icons if the pinned Streamlit
   version supports them (check and tell me).
U4 UX behaviours: toast after approve/reject, confirmation dialog on reject,
   truthful st.status steps during extraction, "N items hidden" explanation for
   Incoming, empty states per section 3.
U5 Verification: write a small script that computes WCAG contrast ratios for every
   text/background token pair and report/fix any under 4.5:1; add a pytest that
   the badge helpers escape HTML (a "<script>alert(1)</script>" input must come
   out escaped); run all existing tests; run the app in a fresh clone; with
   Playwright if available take before/after screenshots at 375, 768 and 1440 px
   into qa/ui/ and report any layout break or horizontal scroll.
Explain to me in plain words: design tokens, config.toml theming vs CSS
injection, data-testid selectors, contrast ratio, and why html.escape matters.
Stop after U5; do not push.
```

---

## 9. For the final submission
- Add a short **"Design and usability"** section to the PDF: the orientation system (rail, role badge, next-step banner), accessibility choices, and before/after screenshots.
- Mention in the testing notes: contrast check, escape test, mobile check.


