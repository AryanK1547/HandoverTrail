import sqlite3
import os
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("HANDOVERTRAIL_DB", PROJECT_ROOT / "handovertrail.db")).expanduser()


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Establishes and returns a connection to the SQLite database.
    Enforces foreign key constraint enforcement in SQLite."""
    configured_path = Path(
        db_path if db_path is not None else os.environ.get("HANDOVERTRAIL_DB", DB_PATH)
    ).expanduser()
    configured_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(configured_path)
    # Enable foreign key constraint support for SQLite
    conn.execute("PRAGMA foreign_keys = ON;")
    # Return rows as dictionary-like objects for easier field access
    conn.row_factory = sqlite3.Row
    return conn


def bootstrap(db_path: str | Path | None = None) -> None:
    """Create the schema, apply additive migrations, and seed demo identities/project."""
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
        sensitivity TEXT NOT NULL DEFAULT 'restricted' CHECK(sensitivity IN ('public', 'restricted')),
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

    source_columns = {
        row["name"] for row in cursor.execute("PRAGMA table_info(sources)").fetchall()
    }
    if "sensitivity" not in source_columns:
        cursor.execute(
            "ALTER TABLE sources ADD COLUMN sensitivity TEXT NOT NULL DEFAULT 'restricted'"
        )

    now = datetime.now().isoformat()
    cursor.executemany("""
        INSERT OR IGNORE INTO users (user_id, name, email, role, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, [
        ("USR-DEMO-ADMIN", "Demo Admin", "admin@demo.local", "Admin", now),
        ("USR-DEMO-REVIEWER", "Demo Reviewer", "reviewer@demo.local", "Reviewer", now),
        ("USR-DEMO-INCOMING", "Demo Incoming", "incoming@demo.local", "Incoming", now),
    ])
    cursor.execute("""
        INSERT OR IGNORE INTO projects (project_id, name, description, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        "PROJ-DEMO-001",
        "Demo Project (Team Techtones)",
        "HandoverTrail MVP Demonstration Project",
        now,
        now,
    ))

    conn.commit()
    conn.close()


def init_db(db_path: str | Path | None = None) -> None:
    """Backward-compatible alias for bootstrap()."""
    bootstrap(db_path)


if __name__ == "__main__":
    bootstrap()
    print("Database successfully initialized at:", DB_PATH)