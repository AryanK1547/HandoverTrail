import sqlite3
import os
import json
import uuid
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
        source_type TEXT NOT NULL DEFAULT 'source',
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
        claim_source TEXT NOT NULL DEFAULT 'generated',
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

    # Round 3 tables use additive creation so later feature migrations preserve existing data.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS claim_versions (
        id TEXT PRIMARY KEY,
        claim_id TEXT NOT NULL,
        version INTEGER NOT NULL,
        text TEXT NOT NULL,
        editor_id TEXT NOT NULL,
        reason TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (claim_id, version),
        FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE,
        FOREIGN KEY (editor_id) REFERENCES users(user_id)
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS claim_slots (
        claim_id TEXT NOT NULL,
        subject TEXT NOT NULL,
        attribute TEXT NOT NULL,
        value TEXT NOT NULL,
        normalized_value TEXT NOT NULL,
        PRIMARY KEY (claim_id, subject, attribute, value),
        FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS claim_conflicts (
        conflict_id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        subject TEXT NOT NULL,
        attribute TEXT NOT NULL,
        claim_a TEXT NOT NULL,
        claim_b TEXT NOT NULL,
        status TEXT NOT NULL,
        resolution TEXT NOT NULL DEFAULT 'UNRESOLVED',
        resolved_by TEXT,
        resolved_at TEXT,
        created_at TEXT NOT NULL,
        UNIQUE (project_id, subject, attribute, claim_a, claim_b),
        FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE,
        FOREIGN KEY (claim_a) REFERENCES claims(claim_id) ON DELETE CASCADE,
        FOREIGN KEY (claim_b) REFERENCES claims(claim_id) ON DELETE CASCADE,
        FOREIGN KEY (resolved_by) REFERENCES users(user_id)
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gaps (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        gap_type TEXT NOT NULL,
        subject TEXT,
        related_claim_id TEXT,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE,
        FOREIGN KEY (related_claim_id) REFERENCES claims(claim_id) ON DELETE SET NULL
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id TEXT PRIMARY KEY,
        gap_id TEXT NOT NULL,
        text TEXT NOT NULL,
        status TEXT NOT NULL,
        assigned_role TEXT NOT NULL,
        assigned_user_id TEXT,
        created_by TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (gap_id) REFERENCES gaps(id) ON DELETE CASCADE,
        FOREIGN KEY (created_by) REFERENCES users(user_id),
        FOREIGN KEY (assigned_user_id) REFERENCES users(user_id)
    );
    """)
    question_columns = {
        row["name"] for row in cursor.execute("PRAGMA table_info(questions)").fetchall()
    }
    if "assigned_user_id" not in question_columns:
        cursor.execute(
            "ALTER TABLE questions ADD COLUMN assigned_user_id TEXT REFERENCES users(user_id)"
        )
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS answers (
        id TEXT PRIMARY KEY,
        question_id TEXT NOT NULL,
        text TEXT NOT NULL,
        author_id TEXT NOT NULL,
        source_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
        FOREIGN KEY (author_id) REFERENCES users(user_id),
        FOREIGN KEY (source_id) REFERENCES sources(source_id)
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS handover_versions (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        version INTEGER NOT NULL,
        released_by TEXT NOT NULL,
        released_at TEXT NOT NULL,
        snapshot_json TEXT NOT NULL,
        UNIQUE (project_id, version),
        FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE,
        FOREIGN KEY (released_by) REFERENCES users(user_id)
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS handover_acks (
        id TEXT PRIMARY KEY,
        handover_version_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        acknowledged_at TEXT NOT NULL,
        UNIQUE (handover_version_id, user_id),
        FOREIGN KEY (handover_version_id) REFERENCES handover_versions(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    """)
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS handover_versions_no_update
    BEFORE UPDATE ON handover_versions
    BEGIN
        SELECT RAISE(ABORT, 'Released handover snapshots are immutable');
    END;
    """)
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS handover_versions_no_delete
    BEFORE DELETE ON handover_versions
    BEGIN
        SELECT RAISE(ABORT, 'Released handover snapshots are immutable');
    END;
    """)
    # The legacy users.role CHECK is intentionally unchanged; this extension supports new roles additively.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_role_assignments (
        user_id TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('Admin', 'Reviewer', 'Incoming', 'Departing')),
        PRIMARY KEY (user_id, role),
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );
    """)

    source_columns = {
        row["name"] for row in cursor.execute("PRAGMA table_info(sources)").fetchall()
    }
    if "sensitivity" not in source_columns:
        cursor.execute(
            "ALTER TABLE sources ADD COLUMN sensitivity TEXT NOT NULL DEFAULT 'restricted'"
        )
    if "source_type" not in source_columns:
        cursor.execute(
            "ALTER TABLE sources ADD COLUMN source_type TEXT NOT NULL DEFAULT 'source'"
        )
    claim_columns = {
        row["name"] for row in cursor.execute("PRAGMA table_info(claims)").fetchall()
    }
    if "claim_source" not in claim_columns:
        cursor.execute(
            "ALTER TABLE claims ADD COLUMN claim_source TEXT NOT NULL DEFAULT 'generated'"
        )

    now = datetime.now().isoformat()
    cursor.executemany("""
        INSERT OR IGNORE INTO users (user_id, name, email, role, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, [
        ("USR-DEMO-ADMIN", "Demo Admin", "admin@demo.local", "Admin", now),
        ("USR-DEMO-REVIEWER", "Demo Reviewer", "reviewer@demo.local", "Reviewer", now),
        ("USR-DEMO-INCOMING", "Demo Incoming", "incoming@demo.local", "Incoming", now),
        ("USR-DEMO-DEPARTING", "Demo Departing", "departing@demo.local", "Incoming", now),
    ])
    cursor.execute(
        """
        INSERT OR IGNORE INTO user_role_assignments (user_id, role)
        VALUES ('USR-DEMO-DEPARTING', 'Departing')
        """
    )
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
    _seed_empty_demo_database(db_path)
    from round3_demo import seed_conflict_demo

    seed_conflict_demo(db_path)


def _seed_empty_demo_database(db_path: str | Path | None = None) -> None:
    project_id = "PROJ-DEMO-001"
    conn = get_connection(db_path)
    source_count = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    evidence_count = conn.execute("SELECT COUNT(*) FROM evidence_chunks").fetchone()[0]
    claim_count = conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
    if source_count or evidence_count or claim_count:
        conn.close()
        return

    demo_dir = PROJECT_ROOT / "data" / "demo_project"
    demo_files = sorted(
        path for path in demo_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".txt", ".csv"}
    )
    if not demo_files:
        conn.close()
        raise FileNotFoundError(f"No demo source files found in {demo_dir}")

    source_ids = []
    now = datetime.now().isoformat()
    for path in demo_files:
        source_id = f"SRC-{uuid.uuid4().hex[:8].upper()}"
        sensitivity = "restricted" if path.name == "restricted_demo.txt" else "public"
        conn.execute(
            """
            INSERT INTO sources
                (source_id, project_id, file_name, file_type, uploaded_at, sensitivity)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (source_id, project_id, path.name, path.suffix[1:].upper(), now, sensitivity),
        )
        source_ids.append(source_id)
    conn.commit()
    conn.close()

    from source_parser import parse_and_store_sources

    parse_and_store_sources(
        project_id,
        source_ids=source_ids,
        db_path=db_path,
        prefer_demo=True,
    )
    _seed_cached_demo_claims(db_path)


def _seed_cached_demo_claims(db_path: str | Path | None = None) -> None:
    cache_path = PROJECT_ROOT / "data" / "demo_cache" / "claims.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    project_id = "PROJ-DEMO-001"
    if cache.get("project_id") != project_id:
        raise ValueError(f"Cached claims must target {project_id}.")

    conn = get_connection(db_path)
    if conn.execute(
        "SELECT COUNT(*) FROM claims WHERE project_id = ?", (project_id,)
    ).fetchone()[0]:
        conn.close()
        return

    evidence_by_location = {
        (row["file_name"], row["chunk_index"]): row["evidence_id"]
        for row in conn.execute(
            """
            SELECT s.file_name, e.chunk_index, e.evidence_id
            FROM evidence_chunks e
            JOIN sources s ON e.source_id = s.source_id
            WHERE s.project_id = ?
            """,
            (project_id,),
        )
    }
    now = datetime.now().isoformat()
    for cached_claim in cache.get("claims", []):
        evidence_ids = []
        for reference in cached_claim.get("evidence", []):
            location = (reference.get("source_file"), reference.get("chunk_index"))
            evidence_id = evidence_by_location.get(location)
            if evidence_id is None:
                conn.close()
                raise ValueError(
                    f"Cached claim references missing demo evidence: {location[0]} chunk {location[1]}."
                )
            evidence_ids.append(evidence_id)
        if not evidence_ids:
            conn.close()
            raise ValueError("Every cached demo claim must include at least one evidence link.")

        claim_id = f"CLM-{uuid.uuid4().hex[:8].upper()}"
        conn.execute(
            """
            INSERT INTO claims
                (claim_id, project_id, claim_text, claim_type, trust_status, claim_source,
                 review_status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'cached_demo', 'PENDING', ?, ?)
            """,
            (
                claim_id,
                project_id,
                cached_claim["claim_text"],
                cached_claim["claim_type"],
                "SINGLE_SOURCE",
                now,
                now,
            ),
        )
        conn.executemany(
            "INSERT INTO claim_evidence (claim_id, evidence_id) VALUES (?, ?)",
            [(claim_id, evidence_id) for evidence_id in sorted(set(evidence_ids))],
        )
    conn.commit()
    conn.close()


def init_db(db_path: str | Path | None = None) -> None:
    """Backward-compatible alias for bootstrap()."""
    bootstrap(db_path)


if __name__ == "__main__":
    bootstrap()
    print("Database successfully initialized at:", DB_PATH)