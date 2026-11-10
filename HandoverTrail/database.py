import sqlite3
import os
from datetime import datetime

# Default database path in the current directory
DB_PATH = "handovertrail.db"


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Establishes and returns a connection to the SQLite database.
    Enforces foreign key constraint enforcement in SQLite."""
    conn = sqlite3.connect(db_path)
    # Enable foreign key constraint support for SQLite
    conn.execute("PRAGMA foreign_keys = ON;")
    # Return rows as dictionary-like objects for easier field access
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    """Creates all 8 required logical tables for HandoverTrail if they do not exist."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # 1. USERS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('Admin', 'Reviewer', 'Incoming')),
        created_at TEXT NOT NULL
    );
    """)

    # 2. PROJECTS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        project_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    # 3. SOURCES TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sources (
        source_id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        file_name TEXT NOT NULL,
        file_type TEXT NOT NULL,
        uploaded_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
    );
    """)

    # 4. EVIDENCE CHUNKS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS evidence_chunks (
        evidence_id TEXT PRIMARY KEY,
        source_id TEXT NOT NULL,
        chunk_index INTEGER NOT NULL,
        excerpt TEXT NOT NULL,
        reference_location TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (source_id) REFERENCES sources(source_id) ON DELETE CASCADE
    );
    """)

    # 5. CLAIMS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS claims (
        claim_id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        claim_text TEXT NOT NULL,
        claim_type TEXT NOT NULL CHECK(claim_type IN ('Decision', 'Owner', 'Risk', 'Dependency', 'Blocker', 'Open question', 'Next action')),
        trust_status TEXT NOT NULL CHECK(trust_status IN ('VERIFIED', 'SINGLE_SOURCE', 'CONFLICTING', 'MISSING_EVIDENCE')),
        review_status TEXT NOT NULL CHECK(review_status IN ('PENDING', 'APPROVED', 'REJECTED', 'EDITED_PENDING_REVIEW')),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
    );
    """)

    # 6. CLAIM EVIDENCE (JUNCTION TABLE FOR MANY-TO-MANY RELATIONSHIP)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS claim_evidence (
        claim_id TEXT NOT NULL,
        evidence_id TEXT NOT NULL,
        PRIMARY KEY (claim_id, evidence_id),
        FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE,
        FOREIGN KEY (evidence_id) REFERENCES evidence_chunks(evidence_id) ON DELETE CASCADE
    );
    """)

    # 7. REVIEWS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        review_id TEXT PRIMARY KEY,
        claim_id TEXT NOT NULL,
        reviewer_id TEXT NOT NULL,
        action TEXT NOT NULL CHECK(action IN ('APPROVED', 'REJECTED', 'EDITED')),
        comment TEXT,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE,
        FOREIGN KEY (reviewer_id) REFERENCES users(user_id) ON DELETE CASCADE
    );
    """)

    # 8. AUDIT LOGS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        log_id TEXT PRIMARY KEY,
        actor_id TEXT NOT NULL,
        action TEXT NOT NULL,
        target_type TEXT NOT NULL,
        target_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (actor_id) REFERENCES users(user_id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database successfully initialized at:", os.path.abspath(DB_PATH))