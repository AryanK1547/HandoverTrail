# HandoverTrail

> **AI-Powered Project Handover & Knowledge Continuity Platform**  
> *Built for Hackathons & Engineering Teams to Eliminate Knowledge Loss During Team Transitions.*

---

## 📌 Overview

Team transitions and handovers are often messy. Critical project context is scattered across disparate chat logs, unorganized meeting notes, scattered task boards, and undocumented code changes, leading to severe onboarding friction and lost institutional knowledge.

**HandoverTrail** solves this by acting as an intelligent handover pipeline. It ingests raw project artifacts (meeting transcripts, chat exports, task sheets, documentation), parses and extracts verifiable project claims using **Google Gemini**, validates evidence trust markers through a hybrid human-in-the-loop review workflow, and generates context-aware, role-appropriate handovers for incoming members.

---

## 🏗️ Core Workflow

1. **Connect & Upload Sources:** Ingest project files (Markdown, text logs, meeting notes, CSVs).
2. **Knowledge Reconstruction:** Parse documents into source-aware chunks and extract candidate claims via Gemini.
3. **Evidence Grounding:** Link every claim directly to its exact source text excerpt.
4. **Trust Validation:** Automatically flag claims as `VERIFIED`, `SINGLE_SOURCE`, `CONFLICTING`, or `MISSING_EVIDENCE`.
5. **Human Review & Approval:** Reviewers inspect, edit, approve, or reject claims before final sign-off.
6. **Role-Based Handover:** Provide incoming team members with clean, verified, role-specific handover briefs complete with open risks and action items.

---

## 🛠️ Tech Stack & Architecture

* **Frontend & UI:** [Streamlit](https://streamlit.io/) (Python-based interactive web app)
* **Backend Logic & AI Extraction:** Python 3.11+, **Google Gemini API** (`google-generativeai`)
* **Storage & Persistence:** 
  * *Local Development / Demo:* SQLite (lightweight, zero-config, reproducible via seed data)
  * *Cloud Production (Optional):* PostgreSQL / Supabase
* **Deployment:** Streamlit Community Cloud & GitHub

---

## 📂 Project Directory Structure

```text
HandoverTrail/
├── app.py                 # Main Streamlit application entry point
├── database.py            # Database connection & schema management (SQLite/Postgres)
├── models.py              # Data models and structures
├── source_parser.py       # Ingestion and parsing logic for uploaded files
├── retrieval.py           # Excerpt search and retrieval logic
├── extractor.py           # Gemini API integration for claim extraction
├── validator.py           # Evidence trust status checks
├── permissions.py         # Role-based access control helpers
├── handover.py            # Handover generation logic
├── requirements.txt       # Python package dependencies
└── README.md              # Project documentation