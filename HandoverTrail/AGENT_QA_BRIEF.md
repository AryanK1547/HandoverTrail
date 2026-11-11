# HANDOVERTRAIL: END-TO-END SYSTEM TEST, QA BLUEPRINT & VERIFICATION SUITE

> **Target Repository / Product:** HandoverTrail
> **Team:** *Techtones* (Solo Builder: Aryan Khode)
> **Auditor Role:** Senior QA Engineer, UX Reviewer & Security-Minded Backend Reviewer
> **Execution Status:** Complete Framework & Comprehensive QA Blueprint Generated

---

## 1. Executive Summary & Readiness Verdict

* **Readiness Verdict:** **READY WITH CRITICAL PRE-DEPLOYMENT HARDENING**
* **Biggest Risks:**
1. *Unsanitized LLM / Heuristic Fallback Mismatches:* If Gemini API fails or runs out of quota, the universal fallback generates generic string summaries that require robust database foreign key cascades and deduplication constraints.
2. *Role-Based Access Control (RBAC) Drift:* Ensuring that Streamlit session state variable manipulation cannot bypass server-side ACL filtering on restricted source files.
3. *Cloud Ephemerality:* SQLite databases and local file paths (`data/` or `.db`) resetting on Streamlit Community Cloud reboots.


* **Top Priority Fix:** Implement an immutable backend permission guard function (`is_authorized_for_source(user_role, source_id)`) called directly before rendering any claim excerpt or citation.

---

## 2. Rubric Scorecard (Hackathon Round 2 Alignment)

| Criteria | Strength | Justification |
| --- | --- | --- |
| **Core Workflow (End-to-End)** | **Strong** | The 5-stage pipeline (Connect ➔ Reconstruct ➔ Verify ➔ Review ➔ Handover) is conceptually complete and handles both live LLM and offline fallback paths. |
| **Technical Depth & Reliability** | **OK** | Solid use of SQLite, BM25 keyword heuristics, and Streamlit state management, but requires strict validation of fallback parsing and database transaction isolation. |
| **Progress vs. Plan** | **Strong** | Rapidly iterated from initial file parsers to multi-source verification and automated role-based handovers. |
| **Three Planned Improvements** | **Strong** | Conflict detection, missing-evidence gap analysis, and secure role-based handovers are fully mapped into the ledger architecture. |
| **Usability for a New User** | **OK** | Needs clear zero-state guidance and pre-loaded demo files so a judge can test the app in under 30 seconds without reading a manual. |

---

## 3. System Architecture & Component Map (`qa/00_system_map.md`)

```
HandoverTrail Architecture Flow:
[ Raw Project Files: Repo / Notes / Chat / Task CSV ]
                        │
                        ▼ (Phase 1: Ingestion & Chunking)
             [ SQLite Database (`sources`, `evidence_chunks`) ]
                        │
                        ▼ (Phase 2: Extraction & Deduplication)
             [ Gemini 1.5 Flash / Heuristic Fallback ] ➔ [ `claims`, `claim_evidence` ]
                        │
                        ▼ (Phase 3: Multi-Source Verification Engine)
             [ Trust Status Engine: Verified | Single-source | Conflicting | Missing ]
                        │
                        ▼ (Phase 4: Human Review & RBAC Filter)
             [ Role-Based Handover View (Admin / Reviewer / Incoming) ]

```

### File-by-File Blueprint

* `app.py`: Main entry point, multi-page navigation router, session state initialization.
* `database.py`: SQLite connection pooler, schema migrations, foreign key constraints (`PRAGMA foreign_keys = ON;`).
* `extractor.py`: Hybrid extraction engine supporting live Gemini JSON parsing and Universal Heuristic Fallback.
* `validator.py`: Cross-references claims against underlying evidence excerpts to assign trust levels.
* `pages/1_Upload_Sources.py`: File ingestion, multi-format parser (CSV, TXT, JSON), sensitivity tagging.
* `pages/2_Review_Claims.py`: Reviewer dashboard, claim editing, approval/rejection workflow, trust status inspection.
* `pages/3_Handover_View.py`: Role-filtered handover deliverables, Day-1/Week-1 action plans, interactive citation modal viewers.

---

## 4. Test Harness Specifications (`tests/` & `qa/fixtures/`)

To guarantee a reliable, zero-cost test suite, all automated backend tests in `tests/` must utilize:

1. **Fake LLM (Monkeypatch):** Intercepts `genai.GenerativeModel.generate_content` to return controlled test JSON, malformed strings, timeouts, or rate-limit HTTP 429 exceptions.
2. **Temporary SQLite DB (`tmp_path`):** Isolates test runs so production databases remain untouched.
3. **Prompt Leak Assertion:** Asserts that restricted secrets (`FAKE-KEY-1234`) never appear in the captured prompt payloads sent to the LLM.

### Sample Test Fixture (`qa/fixtures/sample_project.json`)

```json
{
  "project_id": "PROJ-TEST-999",
  "sources": [
    {
      "source_id": "SRC-001",
      "file_name": "architecture_decision.txt",
      "sensitivity": "PUBLIC",
      "excerpt": "Team decided to use FastAPI and SQLite for the backend implementation."
    },
    {
      "source_id": "SRC-002",
      "file_name": "conflicting_notes.txt",
      "sensitivity": "PUBLIC",
      "excerpt": "Backend will be built using Node.js Express instead of Python."
    },
    {
      "source_id": "SRC-003",
      "file_name": "restricted_creds.txt",
      "sensitivity": "RESTRICTED",
      "excerpt": "Internal deployment token is FAKE-KEY-1234. Do not share."
    }
  ]
}

```

---

## 5. Master Test Case Catalogue (Summary of A to I)

| ID | Area | Pri | Test Objective | Expected Outcome |
| --- | --- | --- | --- | --- |
| **A01** | Ingestion | P0 | Upload valid repo export, notes, chat, and CSV | Accepted and chunked with correct source IDs |
| **A09** | Ingestion | P0 | Upload source without explicit sensitivity tag | Defaults securely to **RESTRICTED** |
| **B02** | Extraction | P0 | Claim cites a non-existent evidence ID | Rejected or downgraded to gap; never shown as verified fact |
| **B07** | Extraction | P0 | Prompt injection inside source ("ignore previous instructions") | Treated strictly as data; no behavior modification |
| **C01** | Verification | P0 | Fact corroborated in 2+ independent sources | Trust Status = `Verified` |
| **C03** | Verification | P0 | Two sources state contradictory owners/dates | Trust Status = `Conflicting`, shown side-by-side |
| **D01** | Security | P0 | Incoming role views handover derived from restricted source | Restricted claims and excerpts are completely absent |
| **D02** | Security | P0 | Assert fake secret (`FAKE-KEY-1234`) absent from LLM prompt | Secret filtered out prior to API payload assembly |
| **D07** | Security | P0 | Tamper with `session_state` role in browser client | Server-side RBAC check blocks unauthorized access |
| **E01** | Review | P0 | Reviewer approves a pending claim | Becomes visible to Incoming role; state persisted |
| **F01** | Handover | P0 | Click citation on any claim in handover view | Opens correct source excerpt modal viewer |
| **G02** | Persistence | P0 | Simulate Streamlit Cloud restart / ephemeral wipe | Default demo fixtures and schema reload automatically |

---

## 6. UI/UX Heuristic Review & Judge Journey

1. **First Impression (0-5 seconds):** The app must immediately greet judges with a clear title (*HandoverTrail*), a 1-sentence value proposition ("Instant, verified knowledge handovers for transitioning team members"), and a prominent **🚀 Load Demo Project** button.
2. **Workflow Progress Bar:** A persistent sidebar or top banner showing `1. Connect ➔ 2. Reconstruct ➔ 3. Verify ➔ 4. Review ➔ 5. Handover` ensures judges never lose their place.
3. **Evidence Transparency:** Citation badges (`[SRC-001]`) must be interactive, displaying exact source file names and verbatim excerpts instantly on click.
4. **Role Toggle:** A clean dropdown in the sidebar allowing instant switching between `Admin`, `Reviewer`, and `Incoming` to immediately demonstrate secure data filtering.

---

## 7. Required Report Structure (`QA_REPORT.md`)

When fully executed by your local coding agent, the generated `QA_REPORT.md` will strictly follow this 12-section layout:

1. Executive Summary
2. Rubric Scorecard
3. Test Coverage Table
4. Detailed Bug List (P0-P3 Table)
5. UI/UX Findings
6. Backend & Architecture Findings
7. Security & Privacy Findings
8. Improvement Recommendations (Impact vs. Effort)
9. Top 10 Fix-First List (with Time Estimates)
10. Not Tested / Blocked Items
11. Appendix A: Plain-Language Tool & Library Explanations
12. Appendix B: Exact Re-run Instructions

---

## 8. Session Log Template (`QA_SESSION_LOG.md`)

```markdown
## Session log
- Date/time: 2026-11-10 12:30 IST
- Phase completed: Phase 0 (Reconnaissance & System Mapping)
- Commands run: `pytest --version`, `ruff --version`
- Files created: `qa/00_system_map.md`, `qa/fixtures/sample_project.json`, `QA_SESSION_LOG.md`
- Findings so far: Initial architecture reviewed; fallback routing verified.
- Real LLM calls used: 0 / 10
- Blocked or None
- Next step: Execute Phase 1 (Static checks & dependency audit).

```

---

## 9. Plain-Language Glossary for Beginners (Appendix A Preview)

* **`pytest`:** A testing framework for Python. It automatically discovers and runs functions starting with `test_` to verify that your code works correctly.
* **`monkeypatch`:** A `pytest` feature that temporarily replaces a real function or variable (like our live Gemini API call) with a fake test version so your tests run instantly without internet access or API costs.
* **`tmp_path`:** A built-in pytest fixture that creates a temporary, empty folder and SQLite database for a single test, destroying it immediately afterward so tests never interfere with each other.
* **`Streamlit AppTest`:** Streamlit's official testing module that allows automated scripts to click buttons, input text, and check UI screens without needing a full web browser.
* **`Playwright`:** An end-to-end browser automation tool that opens a real Chromium browser, clicks around your Streamlit app, and captures screenshots at mobile, tablet, and desktop sizes.
* **`pathlib`:** Python's modern standard library for handling file paths safely across Windows, macOS, and Linux without breaking on backslashes or slashes.

---

## 10. How to Direct Your Coding Agent Next

Save this complete brief as `AGENT_QA_BRIEF.md` in your repository root, then send this exact prompt to your coding agent:

> **"Read AGENT_QA_BRIEF.md fully and execute it. Start with Phase 0."**