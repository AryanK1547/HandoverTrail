from __future__ import annotations

import json
from pathlib import Path

import pytest

import database
import permissions
import retrieval
import source_parser
import validator


PROJECT_ID = "PROJ-QA-001"


@pytest.fixture
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "handovertrail-test.db"
    monkeypatch.setenv("HANDOVERTRAIL_DB", str(db_path))
    database.bootstrap()
    return db_path


def _create_project() -> None:
    conn = database.get_connection()
    conn.execute(
        """
        INSERT INTO projects (project_id, name, description, created_at, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (PROJECT_ID, "QA test project", "Temporary test fixture"),
    )
    conn.commit()
    conn.close()


def _create_source(
    source_id: str,
    file_name: str,
    sensitivity: str,
    excerpt: str,
    chunk_index: int = 0,
) -> str:
    conn = database.get_connection()
    conn.execute(
        """
        INSERT INTO sources
            (source_id, project_id, file_name, file_type, uploaded_at, sensitivity)
        VALUES (?, ?, ?, 'TXT', CURRENT_TIMESTAMP, ?)
        """,
        (source_id, PROJECT_ID, file_name, sensitivity),
    )
    evidence_id = f"EVD-{source_id}"
    conn.execute(
        """
        INSERT INTO evidence_chunks
            (evidence_id, source_id, chunk_index, excerpt, reference_location, created_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (evidence_id, source_id, chunk_index, excerpt, file_name),
    )
    conn.commit()
    conn.close()
    return evidence_id


def _create_claim(
    claim_id: str,
    evidence_ids: list[str] | None = None,
    review_status: str = "PENDING",
) -> None:
    conn = database.get_connection()
    conn.execute(
        """
        INSERT INTO claims
            (claim_id, project_id, claim_text, claim_type, trust_status,
             review_status, created_at, updated_at)
        VALUES (?, ?, ?, 'Decision', 'SINGLE_SOURCE', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (claim_id, PROJECT_ID, f"Claim {claim_id}", review_status),
    )
    conn.executemany(
        "INSERT INTO claim_evidence (claim_id, evidence_id) VALUES (?, ?)",
        [(claim_id, evidence_id) for evidence_id in evidence_ids or []],
    )
    conn.commit()
    conn.close()


def test_cold_start_claims_are_labeled_cached_demo(isolated_db: Path) -> None:
    claims = retrieval.get_visible_claims("Reviewer", "PROJ-DEMO-001")

    assert len(claims) == 4
    assert all(claim["claim_source"] == "cached_demo" for claim in claims)


def test_cached_claims_match_their_committed_demo_evidence(isolated_db: Path) -> None:
    cache_path = database.PROJECT_ROOT / "data" / "demo_cache" / "claims.json"
    cached_claims = json.loads(cache_path.read_text(encoding="utf-8"))["claims"]
    conn = database.get_connection()
    evidence = {
        (row["file_name"], row["chunk_index"]): row["excerpt"]
        for row in conn.execute(
            """
            SELECT s.file_name, e.chunk_index, e.excerpt
            FROM evidence_chunks e
            JOIN sources s ON s.source_id = e.source_id
            WHERE s.project_id = 'PROJ-DEMO-001' AND s.sensitivity = 'public'
            """
        )
    }
    conn.close()

    expected_support = {
        "Stripe over PayPal": {
            ("chat_export.txt", 0): "officially go with Stripe",
            ("meeting_notes.txt", 1): "PayPal evaluation is closed",
            ("tasks.csv", 2): "Evaluate PayPal vs Stripe",
        },
        "T-103": {
            ("tasks.csv", 3): "Design Custom Crypto Blockchain System",
            ("chat_export.txt", 1): "build our own crypto blockchain",
        },
        "T-100": {
            ("tasks.csv", 0): "Backend Stripe API Setup",
            ("repository_export.txt", 1): "Added stripe-node SDK",
            ("meeting_notes.txt", 1): "Sarah will lead the backend Stripe API integration",
        },
        "T-101": {
            ("meeting_notes.txt", 2): "legacy user database schema isn't compatible",
            ("tasks.csv", 1): "Legacy User DB Migration",
            ("repository_export.txt", 1): "Issue #12 (OPEN)",
            ("repository_export.txt", 2): "freezing during the user table migration",
        },
    }
    for marker, expected_excerpts in expected_support.items():
        claim = next(item for item in cached_claims if marker in item["claim_text"])
        references = {
            (item["source_file"], item["chunk_index"])
            for item in claim["evidence"]
        }
        assert references == set(expected_excerpts)
        for location, excerpt_text in expected_excerpts.items():
            assert excerpt_text in evidence[location]


def test_incoming_cannot_see_claim_with_any_restricted_source(isolated_db: Path) -> None:
    _create_project()
    public = _create_source("SRC-PUBLIC", "public.txt", "public", "Public evidence")
    restricted = _create_source("SRC-RESTRICTED", "restricted.txt", "restricted", "Private evidence")
    _create_claim("CLM-MIXED", [public, restricted], "APPROVED")

    assert retrieval.get_visible_claims("Incoming", PROJECT_ID) == []
    assert retrieval.get_claim_evidence("Incoming", "CLM-MIXED") == []


def test_incoming_sees_approved_public_claims_but_admin_sees_all(isolated_db: Path) -> None:
    _create_project()
    public = _create_source("SRC-PUBLIC", "public.txt", "public", "Public evidence")
    restricted = _create_source("SRC-RESTRICTED", "restricted.txt", "restricted", "Private evidence")
    _create_claim("CLM-PUBLIC", [public], "APPROVED")
    _create_claim("CLM-RESTRICTED", [restricted], "APPROVED")
    _create_claim("CLM-PENDING", [public], "PENDING")
    _create_claim("CLM-REJECTED", [public], "REJECTED")

    incoming_ids = {
        claim["claim_id"] for claim in retrieval.get_visible_claims("Incoming", PROJECT_ID)
    }
    admin_ids = {
        claim["claim_id"] for claim in retrieval.get_visible_claims("Admin", PROJECT_ID)
    }
    assert incoming_ids == {"CLM-PUBLIC"}
    assert admin_ids == {"CLM-PUBLIC", "CLM-RESTRICTED", "CLM-PENDING", "CLM-REJECTED"}


def test_incoming_evidence_excerpts_are_filtered(isolated_db: Path) -> None:
    _create_project()
    public = _create_source("SRC-PUBLIC", "public.txt", "public", "public excerpt")
    restricted = _create_source("SRC-RESTRICTED", "restricted.txt", "restricted", "private excerpt")
    _create_claim("CLM-PUBLIC", [public], "APPROVED")
    _create_claim("CLM-RESTRICTED", [restricted], "APPROVED")

    public_evidence = retrieval.get_claim_evidence("Incoming", "CLM-PUBLIC")
    restricted_evidence = retrieval.get_claim_evidence("Incoming", "CLM-RESTRICTED")
    assert [row["excerpt"] for row in public_evidence] == ["public excerpt"]
    assert restricted_evidence == []


def test_fake_restricted_secret_never_appears_in_incoming_data(isolated_db: Path) -> None:
    fake_secret = next(
        line.removeprefix("Fake secret: ").strip()
        for line in (database.PROJECT_ROOT / "data" / "demo_project" / "restricted_demo.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.startswith("Fake secret: ")
    )
    claims = retrieval.get_visible_claims("Incoming", "PROJ-DEMO-001")
    returned = {
        "sources": retrieval.get_visible_sources("Incoming", "PROJ-DEMO-001"),
        "chunks": retrieval.get_visible_evidence_chunks("Incoming", "PROJ-DEMO-001"),
        "claims": claims,
        "evidence": [
            retrieval.get_claim_evidence("Incoming", claim["claim_id"])
            for claim in claims
        ],
    }

    assert fake_secret not in repr(returned)
    assert all(source["sensitivity"] == "public" for source in returned["sources"])


def test_incoming_review_is_denied_without_claim_or_review_mutation(isolated_db: Path) -> None:
    _create_project()
    public = _create_source("SRC-PUBLIC", "public.txt", "public", "Evidence")
    _create_claim("CLM-DENIED", [public])

    with pytest.raises(PermissionError):
        permissions.perform_claim_review("Incoming", "CLM-DENIED", "APPROVED")

    conn = database.get_connection()
    claim_status = conn.execute(
        "SELECT review_status FROM claims WHERE claim_id = 'CLM-DENIED'"
    ).fetchone()[0]
    review_count = conn.execute(
        "SELECT COUNT(*) FROM reviews WHERE claim_id = 'CLM-DENIED'"
    ).fetchone()[0]
    denied_audit_count = conn.execute(
        "SELECT COUNT(*) FROM audit_logs WHERE target_id = 'CLM-DENIED' AND action = 'DENIED_APPROVED'"
    ).fetchone()[0]
    conn.close()
    assert claim_status == "PENDING"
    assert review_count == 0
    assert denied_audit_count == 1


def test_reviewer_approval_writes_review_and_audit_rows(isolated_db: Path) -> None:
    _create_project()
    public = _create_source("SRC-PUBLIC", "public.txt", "public", "Evidence")
    _create_claim("CLM-APPROVED", [public])

    permissions.perform_claim_review("Reviewer", "CLM-APPROVED", "APPROVED")

    conn = database.get_connection()
    claim_status = conn.execute(
        "SELECT review_status FROM claims WHERE claim_id = 'CLM-APPROVED'"
    ).fetchone()[0]
    review = conn.execute(
        "SELECT reviewer_id, action FROM reviews WHERE claim_id = 'CLM-APPROVED'"
    ).fetchone()
    audit = conn.execute(
        "SELECT actor_id, action FROM audit_logs WHERE target_id = 'CLM-APPROVED'"
    ).fetchone()
    conn.close()
    assert claim_status == "APPROVED"
    assert tuple(review) == ("USR-DEMO-REVIEWER", "APPROVED")
    assert tuple(audit) == ("USR-DEMO-REVIEWER", "APPROVED")


def test_upload_filename_is_sanitized(isolated_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    upload_root = tmp_path / "uploads"
    monkeypatch.setattr(source_parser, "UPLOADS_DIR", upload_root)

    path, replaced = source_parser.persist_uploaded_file(
        PROJECT_ID, "../../x.txt", b"Safe content"
    )

    assert source_parser.sanitize_upload_filename("../../x.txt") == "x.txt"
    assert path == upload_root / PROJECT_ID / "x.txt"
    assert path.read_bytes() == b"Safe content"
    assert replaced is False


def test_empty_upload_is_rejected(isolated_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(source_parser, "UPLOADS_DIR", tmp_path / "uploads")

    with pytest.raises(ValueError, match="is empty"):
        source_parser.persist_uploaded_file(PROJECT_ID, "empty.txt", b"")


def _parse_upload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    file_name: str,
    contents: bytes,
) -> list[str]:
    upload_root = tmp_path / "uploads"
    monkeypatch.setattr(source_parser, "UPLOADS_DIR", upload_root)
    _create_project()
    saved_path, _ = source_parser.persist_uploaded_file(PROJECT_ID, file_name, contents)
    conn = database.get_connection()
    source_id = f"SRC-{file_name}"
    conn.execute(
        """
        INSERT INTO sources
            (source_id, project_id, file_name, file_type, uploaded_at, sensitivity)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, 'public')
        """,
        (source_id, PROJECT_ID, saved_path.name, saved_path.suffix[1:].upper()),
    )
    conn.commit()
    conn.close()
    source_parser.parse_and_store_sources(PROJECT_ID, source_ids=[source_id])
    conn = database.get_connection()
    excerpts = [
        row[0]
        for row in conn.execute(
            "SELECT excerpt FROM evidence_chunks WHERE source_id = ? ORDER BY chunk_index",
            (source_id,),
        )
    ]
    conn.close()
    return excerpts


def test_parser_decodes_utf8_with_bom(isolated_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    excerpts = _parse_upload(tmp_path, monkeypatch, "bom.txt", b"\xef\xbb\xbfcaf\xc3\xa9")

    assert excerpts == ["café"]


def test_parser_falls_back_to_latin1(isolated_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    excerpts = _parse_upload(tmp_path, monkeypatch, "latin1.txt", b"caf\xe9".decode("latin-1").encode("latin-1"))

    assert excerpts == ["café"]


def test_parser_keeps_extra_columns_from_ragged_csv(
    isolated_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    excerpts = _parse_upload(
        tmp_path,
        monkeypatch,
        "ragged.csv",
        b"task_id,title\nT-1,First task,Unexpected value\n",
    )

    assert len(excerpts) == 1
    assert "task_id: T-1" in excerpts[0]
    assert "title: First task" in excerpts[0]
    assert "Extra columns: Unexpected value" in excerpts[0]


def test_validator_trust_status_thresholds(isolated_db: Path) -> None:
    _create_project()
    one_file = _create_source("SRC-ONE", "one.txt", "public", "one")
    two_file = _create_source("SRC-TWO", "two.txt", "public", "two")
    _create_claim("CLM-ZERO")
    _create_claim("CLM-ONE", [one_file])
    _create_claim("CLM-TWO", [one_file, two_file])

    assert validator.validate_project_claims("Reviewer", PROJECT_ID) == 3

    conn = database.get_connection()
    statuses = {
        row["claim_id"]: row["trust_status"]
        for row in conn.execute(
            "SELECT claim_id, trust_status FROM claims WHERE project_id = ?",
            (PROJECT_ID,),
        )
    }
    conn.close()
    assert statuses == {
        "CLM-ZERO": "MISSING_EVIDENCE",
        "CLM-ONE": "SINGLE_SOURCE",
        "CLM-TWO": "VERIFIED",
    }
