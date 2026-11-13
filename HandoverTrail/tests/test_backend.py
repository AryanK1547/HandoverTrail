from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import database
import claim_history
import conflict_detection
import extractor
import handover_release
import interviews
import masking
import permissions
import provider_gateway
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
    claim_text: str | None = None,
    claim_type: str = "Decision",
) -> None:
    conn = database.get_connection()
    conn.execute(
        """
        INSERT INTO claims
            (claim_id, project_id, claim_text, claim_type, trust_status,
             review_status, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'SINGLE_SOURCE', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (claim_id, PROJECT_ID, claim_text or f"Claim {claim_id}", claim_type, review_status),
    )
    conn.executemany(
        "INSERT INTO claim_evidence (claim_id, evidence_id) VALUES (?, ?)",
        [(claim_id, evidence_id) for evidence_id in evidence_ids or []],
    )
    conn.commit()
    conn.close()


def _create_gap(gap_id: str, gap_type: str, subject: str) -> None:
    conn = database.get_connection()
    conn.execute(
        """
        INSERT INTO gaps (id, project_id, gap_type, subject, status, created_at)
        VALUES (?, ?, ?, ?, 'open', CURRENT_TIMESTAMP)
        """,
        (gap_id, PROJECT_ID, gap_type, subject),
    )
    conn.commit()
    conn.close()


def test_round3_schema_migration_is_additive_and_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "legacy-handovertrail.db"
    monkeypatch.setenv("HANDOVERTRAIL_DB", str(db_path))
    conn = database.get_connection()
    conn.executescript("""
        CREATE TABLE projects (
            project_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE sources (
            source_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_type TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );
        CREATE TABLE questions (
            id TEXT PRIMARY KEY,
            gap_id TEXT NOT NULL,
            text TEXT NOT NULL,
            status TEXT NOT NULL,
            assigned_role TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        INSERT INTO projects
            (project_id, name, description, created_at, updated_at)
        VALUES ('PROJ-LEGACY', 'Legacy project', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
        INSERT INTO sources
            (source_id, project_id, file_name, file_type, uploaded_at)
        VALUES ('SRC-LEGACY', 'PROJ-LEGACY', 'legacy.txt', 'TXT', CURRENT_TIMESTAMP);
    """)
    conn.close()

    database.bootstrap()
    database.bootstrap()

    conn = database.get_connection()
    source = conn.execute(
        "SELECT source_id, file_name, sensitivity, source_type FROM sources"
    ).fetchone()
    assert tuple(source) == ("SRC-LEGACY", "legacy.txt", "restricted", "source")

    round3_tables = {
        "claim_versions",
        "claim_slots",
        "claim_conflicts",
        "gaps",
        "questions",
        "answers",
        "handover_versions",
        "handover_acks",
    }
    table_names = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert round3_tables <= table_names
    for table_name in round3_tables:
        assert conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0] == 0
    question_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(questions)")
    }
    assert "assigned_user_id" in question_columns
    assert conn.execute(
        """
        SELECT COUNT(*) FROM user_role_assignments
        WHERE user_id = 'USR-DEMO-DEPARTING' AND role = 'Departing'
        """
    ).fetchone()[0] == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'Reviewer'"
    ).fetchone()[0] == 1
    conn.close()


def test_mask_sensitive_text_redacts_contacts_credentials_and_ids() -> None:
    original = (
        "Contact alice@example.test or +91 98765 43210; "
        "token sk-test-abcdefghijklmnop; ID 123456789012."
    )

    masked, count = masking.mask_sensitive_text(original)

    assert count == 4
    assert "alice@example.test" not in masked
    assert "+91 98765 43210" not in masked
    assert "sk-test-abcdefghijklmnop" not in masked
    assert "123456789012" not in masked
    assert "[REDACTED:email]" in masked
    assert "[REDACTED:phone]" in masked
    assert "[REDACTED:secret]" in masked
    assert "[REDACTED:id]" in masked


def test_mask_sensitive_text_preserves_ordinary_text() -> None:
    text = "The project uses SQLite, and release 3 ships on 15 Nov."

    assert masking.mask_sensitive_text(text) == (text, 0)


def test_provider_gateway_masks_payload_and_rejects_restricted_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_values = (
        "alice@example.test",
        "+91 98765 43210",
        "sk-test-abcdefghijklmnop",
        "AIzaSySyntheticKeyValue1234567890",
        "123456789012",
    )
    captured_prompts = []

    def fake_gemini(api_key: str, model: str, prompt: str) -> str:
        captured_prompts.append(prompt)
        return '{"claims":[]}'

    def fake_openrouter(api_key: str, model: str, prompt: str) -> str:
        captured_prompts.append(prompt)
        return '{"claims":[]}'

    monkeypatch.setattr(provider_gateway, "_invoke_gemini", fake_gemini)
    monkeypatch.setattr(provider_gateway, "_invoke_openrouter", fake_openrouter)
    public_chunk = {
        "evidence_id": "EVD-PUBLIC",
        "file_name": f"{private_values[0]}.txt",
        "reference_location": private_values[1],
        "excerpt": " ".join(private_values[2:]),
        "sensitivity": "public",
    }

    gemini_response = provider_gateway.generate_gemini_response(
        "test-key", "test-model", [public_chunk]
    )
    openrouter_response = provider_gateway.generate_openrouter_response(
        "test-key", "test-model", [public_chunk]
    )

    assert gemini_response.masked_values == 5
    assert openrouter_response.masked_values == 5
    assert len(captured_prompts) == 2
    for prompt in captured_prompts:
        assert all(value not in prompt for value in private_values)
        assert prompt.count("[REDACTED:") == 5
    with pytest.raises(provider_gateway.RestrictedEvidenceError):
        provider_gateway.build_provider_payload([
            {**public_chunk, "sensitivity": "restricted"}
        ])


def test_openrouter_http_request_uses_fake_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_headers = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return json.dumps({
                "choices": [{"message": {"content": "synthetic response"}}]
            }).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured_headers.append(request.get_header("Authorization"))
        return FakeResponse()

    monkeypatch.setattr(provider_gateway.urllib.request, "urlopen", fake_urlopen)

    response = provider_gateway._invoke_openrouter(
        "synthetic-test-key",
        "test-model",
        "safe synthetic prompt",
    )

    assert response == "synthetic response"
    assert captured_headers == ["Bearer synthetic-test-key"]


def test_extraction_sends_only_public_chunks_and_uses_local_restricted_heuristic(
    isolated_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_project()
    public_evidence = _create_source(
        "SRC-PUBLIC-AI",
        "public-ai.txt",
        "public",
        "Decision: SQLite is used. Contact alice@example.test.",
    )
    restricted_evidence = _create_source(
        "SRC-RESTRICTED-AI",
        "restricted-ai.txt",
        "restricted",
        "Task-77 owner is Priya; synthetic credential FAKE-R3-SECRET-0001; "
        "phone +91 98765 43210.",
    )
    captured_prompts = []

    def fake_gemini(api_key: str, model: str, prompt: str) -> str:
        captured_prompts.append(prompt)
        return json.dumps({
            "claims": [{
                "claim_text": "The project uses SQLite.",
                "claim_type": "Decision",
                "evidence_ids": [public_evidence],
            }]
        })

    monkeypatch.setattr(provider_gateway, "_invoke_gemini", fake_gemini)

    result = extractor.extract_claims_from_evidence(
        PROJECT_ID,
        api_key="synthetic-test-key",
    )

    assert result["status"] == "success"
    assert result["method"] == "Gemini API + local restricted-source heuristic"
    assert result["masked_values"] == 1
    assert len(captured_prompts) == 1
    assert "alice@example.test" not in captured_prompts[0]
    assert "Task-77 owner is Priya" not in captured_prompts[0]
    assert "FAKE-R3-SECRET-0001" not in captured_prompts[0]
    assert "+91 98765 43210" not in captured_prompts[0]
    assert "[REDACTED:email]" in captured_prompts[0]

    conn = database.get_connection()
    claims_by_method = {
        row["claim_source"]: row["claim_id"]
        for row in conn.execute(
            "SELECT claim_id, claim_source FROM claims WHERE project_id = ?",
            (PROJECT_ID,),
        )
    }
    assert "Gemini API" in claims_by_method
    assert "Local heuristic (restricted sources)" in claims_by_method
    restricted_claim_id = claims_by_method["Local heuristic (restricted sources)"]
    linked_source = conn.execute(
        """
        SELECT s.sensitivity
        FROM claim_evidence ce
        JOIN evidence_chunks e ON e.evidence_id = ce.evidence_id
        JOIN sources s ON s.source_id = e.source_id
        WHERE ce.claim_id = ?
        """,
        (restricted_claim_id,),
    ).fetchone()
    conn.close()
    assert linked_source["sensitivity"] == "restricted"


def test_provider_failure_uses_labeled_local_fallback(
    isolated_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_project()
    _create_source(
        "SRC-PROVIDER-FAILURE",
        "failure.txt",
        "public",
        "The team confirmed the project uses SQLite. Contact alice@example.test.",
    )

    def failing_gemini(api_key: str, model: str, prompt: str) -> str:
        raise RuntimeError("synthetic provider failure")

    monkeypatch.setattr(provider_gateway, "_invoke_gemini", failing_gemini)

    result = extractor.extract_claims_from_evidence(
        PROJECT_ID,
        api_key="synthetic-test-key",
    )

    assert result["status"] == "success"
    assert result["method"] == "Universal Keyword Fallback"
    assert result["masked_values"] == 1
    conn = database.get_connection()
    methods = {
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT claim_source FROM claims WHERE project_id = ?",
            (PROJECT_ID,),
        )
    }
    conn.close()
    assert methods == {"Universal Keyword Fallback"}, result


def test_incoming_reads_mask_claims_and_public_evidence(isolated_db: Path) -> None:
    _create_project()
    evidence_id = _create_source(
        "SRC-MASKED-INCOMING",
        "notes.txt",
        "public",
        "Contact alice@example.test or +91 98765 43210.",
    )
    _create_claim("CLM-MASKED-INCOMING", [evidence_id], "APPROVED")
    conn = database.get_connection()
    conn.execute(
        "UPDATE claims SET claim_text = ? WHERE claim_id = ?",
        ("Contact alice@example.test", "CLM-MASKED-INCOMING"),
    )
    conn.commit()
    conn.close()

    visible_claim = retrieval.get_visible_claims("Incoming", PROJECT_ID)[0]
    visible_evidence = retrieval.get_claim_evidence(
        "Incoming", "CLM-MASKED-INCOMING"
    )[0]

    assert "alice@example.test" not in visible_claim["claim_text"]
    assert "[REDACTED:email]" in visible_claim["claim_text"]
    assert "alice@example.test" not in visible_evidence["excerpt"]
    assert "+91 98765 43210" not in visible_evidence["excerpt"]
    assert "[REDACTED:email]" in visible_evidence["excerpt"]
    assert "[REDACTED:phone]" in visible_evidence["excerpt"]


def test_cold_start_claims_are_labeled_cached_demo(isolated_db: Path) -> None:
    claims = retrieval.get_visible_claims("Reviewer", "PROJ-DEMO-001")

    assert len(claims) == 13
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


def test_bootstrap_and_demo_paths_work_from_repository_parent(
    isolated_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(database.PROJECT_ROOT.parent)

    database.bootstrap()

    conn = database.get_connection()
    source_count = conn.execute(
        "SELECT COUNT(*) FROM sources WHERE project_id = 'PROJ-DEMO-001'"
    ).fetchone()[0]
    evidence_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM evidence_chunks e
        JOIN sources s ON s.source_id = e.source_id
        WHERE s.project_id = 'PROJ-DEMO-001'
        """
    ).fetchone()[0]
    cached_claim_count = conn.execute(
        "SELECT COUNT(*) FROM claims WHERE project_id = 'PROJ-DEMO-001' AND claim_source = 'cached_demo'"
    ).fetchone()[0]
    conn.close()

    expected_demo_dir = database.PROJECT_ROOT / "data" / "demo_project"
    assert source_count == 8
    assert evidence_count == 17
    assert cached_claim_count == 13
    assert source_parser._source_path(
        "PROJ-DEMO-001",
        "meeting_notes.txt",
        prefer_demo=True,
    ) == expected_demo_dir / "meeting_notes.txt"
    assert source_parser.UPLOADS_DIR == database.PROJECT_ROOT / "uploads"


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
        "CLM-TWO": "SINGLE_SOURCE",
    }


def _create_slot_claim(
    claim_id: str,
    source_id: str,
    file_name: str,
    claim_text: str,
    claim_type: str = "Owner",
) -> None:
    evidence_id = _create_source(source_id, file_name, "public", claim_text)
    _create_claim(
        claim_id,
        [evidence_id],
        claim_text=claim_text,
        claim_type=claim_type,
    )


def test_conflict_detector_flags_disagreeing_owners(isolated_db: Path) -> None:
    _create_project()
    _create_slot_claim(
        "CLM-OWNER-A",
        "SRC-OWNER-A",
        "owner-a.txt",
        "Payment webhook owner is Priya Shah.",
    )
    _create_slot_claim(
        "CLM-OWNER-B",
        "SRC-OWNER-B",
        "owner-b.txt",
        "Payment webhook owner is Alex Chen.",
    )

    conflict_detection.detect_project_conflicts("Reviewer", PROJECT_ID)
    assert validator.validate_project_claims("Reviewer", PROJECT_ID) == 2

    conn = database.get_connection()
    conflict = conn.execute(
        """
        SELECT subject, attribute, status, claim_a, claim_b
        FROM claim_conflicts WHERE project_id = ?
        """,
        (PROJECT_ID,),
    ).fetchone()
    statuses = {
        row["claim_id"]: row["trust_status"]
        for row in conn.execute(
            "SELECT claim_id, trust_status FROM claims WHERE project_id = ?",
            (PROJECT_ID,),
        )
    }
    conn.close()
    assert (conflict["subject"], conflict["attribute"], conflict["status"]) == (
        "Payment webhook",
        "owner",
        "CONFLICTING",
    )
    assert statuses == {"CLM-OWNER-A": "CONFLICTING", "CLM-OWNER-B": "CONFLICTING"}


def test_conflict_detector_normalizes_names_and_dates(isolated_db: Path) -> None:
    _create_project()
    _create_slot_claim(
        "CLM-OWNER-LOWER",
        "SRC-OWNER-LOWER",
        "owner-lower.txt",
        "Payment webhook owner is Priya Shah.",
    )
    _create_slot_claim(
        "CLM-OWNER-UPPER",
        "SRC-OWNER-UPPER",
        "owner-upper.txt",
        "payment webhook owner is PRIYA SHAH.",
    )
    _create_slot_claim(
        "CLM-DATE-WORDS",
        "SRC-DATE-WORDS",
        "date-words.txt",
        "Release deadline is 15 Nov 2026.",
        claim_type="Decision",
    )
    _create_slot_claim(
        "CLM-DATE-ISO",
        "SRC-DATE-ISO",
        "date-iso.txt",
        "Release deadline is 2026-11-15.",
        claim_type="Decision",
    )

    conflict_detection.detect_project_conflicts("Reviewer", PROJECT_ID)
    validator.validate_project_claims("Reviewer", PROJECT_ID)

    conn = database.get_connection()
    rows = conn.execute(
        """
        SELECT attribute, status FROM claim_conflicts
        WHERE project_id = ? ORDER BY attribute
        """,
        (PROJECT_ID,),
    ).fetchall()
    statuses = {
        row["claim_id"]: row["trust_status"]
        for row in conn.execute(
            "SELECT claim_id, trust_status FROM claims WHERE project_id = ?",
            (PROJECT_ID,),
        )
    }
    conn.close()
    assert {(row["attribute"], row["status"]) for row in rows} == {
        ("owner", "CORROBORATED"),
        ("deadline", "CORROBORATED"),
    }
    assert all(value == "VERIFIED" for value in statuses.values())


def test_similar_subject_mismatch_is_labelled_possible_conflict(isolated_db: Path) -> None:
    _create_project()
    _create_slot_claim(
        "CLM-POSSIBLE-A",
        "SRC-POSSIBLE-A",
        "possible-a.txt",
        "Payment webhook owner is Priya Shah.",
    )
    _create_slot_claim(
        "CLM-POSSIBLE-B",
        "SRC-POSSIBLE-B",
        "possible-b.txt",
        "Payment webhooks owner is Alex Chen.",
    )

    conflict_detection.detect_project_conflicts("Reviewer", PROJECT_ID)
    validator.validate_project_claims("Reviewer", PROJECT_ID)

    conn = database.get_connection()
    conflict_status = conn.execute(
        "SELECT status FROM claim_conflicts WHERE project_id = ?",
        (PROJECT_ID,),
    ).fetchone()[0]
    trust_statuses = {
        row["trust_status"]
        for row in conn.execute(
            "SELECT trust_status FROM claims WHERE project_id = ?",
            (PROJECT_ID,),
        )
    }
    conn.close()
    assert conflict_status == "POSSIBLE_CONFLICT"
    assert trust_statuses == {"SINGLE_SOURCE"}


def test_gap_detector_covers_missing_owner_date_rationale_mitigation_and_single_source(
    isolated_db: Path,
) -> None:
    _create_project()
    _create_slot_claim(
        "CLM-GAP-TASK",
        "SRC-GAP-TASK",
        "gap-task.txt",
        "Task T-204 is open and has no owner.",
        claim_type="Next action",
    )
    _create_slot_claim(
        "CLM-GAP-DECISION",
        "SRC-GAP-DECISION",
        "gap-decision.txt",
        "Decision: Switch cache strategy.",
        claim_type="Decision",
    )
    _create_slot_claim(
        "CLM-GAP-RISK",
        "SRC-GAP-RISK",
        "gap-risk.txt",
        "Risk: retries may overload the API.",
        claim_type="Risk",
    )

    conflict_detection.detect_project_conflicts("Reviewer", PROJECT_ID)
    first_gap_count = len(conflict_detection.get_gap_records("Reviewer", PROJECT_ID))
    conflict_detection.detect_project_conflicts("Reviewer", PROJECT_ID)
    gaps = conflict_detection.get_gap_records("Reviewer", PROJECT_ID)
    gap_types = {gap["gap_type"] for gap in gaps}

    assert gap_types == {
        "task_without_owner",
        "decision_missing_date",
        "decision_missing_rationale",
        "risk_missing_mitigation",
        "single_source_claim",
    }
    assert len(gaps) == first_gap_count


def test_conflict_resolution_is_audited(isolated_db: Path) -> None:
    _create_project()
    _create_slot_claim(
        "CLM-RESOLVE-A",
        "SRC-RESOLVE-A",
        "resolve-a.txt",
        "Payment webhook owner is Priya Shah.",
    )
    _create_slot_claim(
        "CLM-RESOLVE-B",
        "SRC-RESOLVE-B",
        "resolve-b.txt",
        "Payment webhook owner is Alex Chen.",
    )
    conflict_detection.detect_project_conflicts("Reviewer", PROJECT_ID)
    conn = database.get_connection()
    conflict_id = conn.execute(
        "SELECT conflict_id FROM claim_conflicts WHERE project_id = ?",
        (PROJECT_ID,),
    ).fetchone()[0]
    conn.close()

    conflict_detection.resolve_conflict("Reviewer", conflict_id, "KEEP_A")

    conn = database.get_connection()
    conflict = conn.execute(
        "SELECT resolution, resolved_by FROM claim_conflicts WHERE conflict_id = ?",
        (conflict_id,),
    ).fetchone()
    audit = conn.execute(
        """
        SELECT actor_id, action, target_type, target_id
        FROM audit_logs WHERE target_id = ?
        """,
        (conflict_id,),
    ).fetchone()
    conn.close()
    assert tuple(conflict) == ("KEEP_A", "USR-DEMO-REVIEWER")
    assert tuple(audit) == (
        "USR-DEMO-REVIEWER",
        "RESOLVE_CONFLICT_KEEP_A",
        "claim_conflict",
        conflict_id,
    )


def test_exit_interview_questions_are_generated_editable_and_role_scoped(
    isolated_db: Path,
) -> None:
    _create_project()
    gap_types = (
        "task_without_owner",
        "decision_missing_date",
        "decision_missing_rationale",
        "risk_missing_mitigation",
        "single_source_claim",
    )
    for index, gap_type in enumerate(gap_types):
        _create_gap(f"GAP-INTERVIEW-{index}", gap_type, f"item {index}")

    assert interviews.generate_questions("Reviewer", PROJECT_ID) == 5
    assert interviews.generate_questions("Reviewer", PROJECT_ID) == 0
    questions = interviews.get_questions("Reviewer", PROJECT_ID)
    assert len(questions) == 5
    assert {question["status"] for question in questions} == {"DRAFT"}
    assert all(question["assigned_user_id"] == interviews.DEPARTING_USER_ID for question in questions)
    assert any("Who will own" in question["text"] for question in questions)
    assert any("When was" in question["text"] for question in questions)
    assert any("Why was" in question["text"] for question in questions)
    assert any("mitigation" in question["text"] for question in questions)
    assert any("another source" in question["text"] for question in questions)

    custom_id = interviews.add_question(
        "Reviewer",
        PROJECT_ID,
        "GAP-INTERVIEW-0",
        "Where is the ownership plan recorded?",
    )
    interviews.update_question("Reviewer", custom_id, "Who will maintain the ownership record?")
    interviews.delete_question("Reviewer", custom_id)
    assert interviews.get_questions("Departing", PROJECT_ID) == []
    assert interviews.send_questions("Reviewer", PROJECT_ID) == 5

    conn = database.get_connection()
    conn.execute(
        """
        INSERT INTO questions
            (id, gap_id, text, status, assigned_role, assigned_user_id, created_by, created_at)
        VALUES ('Q-OTHER-USER', 'GAP-INTERVIEW-0', 'Not assigned to this leaver',
                'SENT', 'Departing', 'USR-DEMO-INCOMING', 'USR-DEMO-REVIEWER', CURRENT_TIMESTAMP)
        """
    )
    conn.commit()
    conn.close()

    departing_questions = interviews.get_questions("Departing", PROJECT_ID)
    assert len(departing_questions) == 5
    assert all(question["status"] == "SENT" for question in departing_questions)
    assert "Q-OTHER-USER" not in {question["id"] for question in departing_questions}
    with pytest.raises(PermissionError):
        interviews.get_questions("Incoming", PROJECT_ID)
    with pytest.raises(PermissionError):
        interviews.generate_questions("Departing", PROJECT_ID)


def test_exit_interview_answer_becomes_scoped_pending_evidence_and_resolves_gap(
    isolated_db: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_project()
    _create_gap("GAP-ANSWER-OWNER", "task_without_owner", "T-55")
    existing_evidence = _create_source(
        "SRC-EXISTING",
        "existing.txt",
        "public",
        "An unrelated existing decision.",
    )
    _create_claim("CLM-EXISTING", [existing_evidence])
    question_id = interviews.add_question(
        "Reviewer",
        PROJECT_ID,
        "GAP-ANSWER-OWNER",
        "Who will own task T-55?",
    )
    interviews.send_questions("Reviewer", PROJECT_ID)
    monkeypatch.setattr(source_parser, "UPLOADS_DIR", tmp_path / "uploads")

    def unexpected_provider_call(*_args, **_kwargs):
        raise AssertionError("Tests must not make provider calls.")

    monkeypatch.setattr(extractor, "generate_gemini_response", unexpected_provider_call)
    monkeypatch.setattr(extractor, "generate_openrouter_response", unexpected_provider_call)
    result = interviews.submit_answer(
        "Departing",
        question_id,
        "The handoff is written in the service runbook.",
        sensitivity="public",
    )

    conn = database.get_connection()
    answer = conn.execute(
        """
        SELECT a.text, a.author_id, a.source_id, a.created_at, s.file_name,
               s.sensitivity, s.source_type, q.status, g.status AS gap_status
        FROM answers a
        JOIN sources s ON s.source_id = a.source_id
        JOIN questions q ON q.id = a.question_id
        JOIN gaps g ON g.id = q.gap_id
        WHERE a.id = ?
        """,
        (result["answer_id"],),
    ).fetchone()
    extracted_claim = conn.execute(
        """
        SELECT c.claim_id, c.claim_text, c.claim_source, c.review_status,
               ce.evidence_id, e.source_id
        FROM claims c
        JOIN claim_evidence ce ON ce.claim_id = c.claim_id
        JOIN evidence_chunks e ON e.evidence_id = ce.evidence_id
        WHERE e.source_id = ? AND c.claim_id <> 'CLM-EXISTING'
        """,
        (result["source_id"],),
    ).fetchone()
    existing_claim = conn.execute(
        "SELECT claim_id FROM claims WHERE claim_id = 'CLM-EXISTING'"
    ).fetchone()
    chunk_count = conn.execute(
        "SELECT COUNT(*) FROM evidence_chunks WHERE source_id = ?",
        (result["source_id"],),
    ).fetchone()[0]
    audit = conn.execute(
        """
        SELECT actor_id, action, target_type, target_id FROM audit_logs
        WHERE target_id = ?
        """,
        (result["answer_id"],),
    ).fetchone()
    conn.close()

    assert answer["author_id"] == interviews.DEPARTING_USER_ID
    assert answer["created_at"]
    assert answer["source_id"] == result["source_id"]
    assert answer["sensitivity"] == "public"
    assert answer["source_type"] == "interview"
    assert answer["status"] == "ANSWERED"
    assert answer["gap_status"] == "answered-pending-review"
    assert chunk_count == 2
    assert extracted_claim["review_status"] == "PENDING"
    assert extracted_claim["claim_text"] == "Interview answer: The handoff is written in the service runbook."
    assert extracted_claim["claim_source"] == "Interview answer (verbatim)"
    assert extracted_claim["source_id"] == result["source_id"]
    assert existing_claim is not None
    assert tuple(audit) == (
        interviews.DEPARTING_USER_ID,
        "SUBMIT_INTERVIEW_ANSWER",
        "answer",
        result["answer_id"],
    )
    assert result["claims_created"] == 1

    incoming_sources = retrieval.get_visible_sources("Incoming", PROJECT_ID)
    incoming_evidence = retrieval.get_visible_evidence_chunks("Incoming", PROJECT_ID)
    assert result["source_id"] not in {source["source_id"] for source in incoming_sources}
    assert result["source_id"] not in {chunk["source_id"] for chunk in incoming_evidence}
    assert extracted_claim["claim_id"] not in {
        claim["claim_id"] for claim in retrieval.get_visible_claims("Incoming", PROJECT_ID)
    }

    permissions.perform_claim_review("Reviewer", extracted_claim["claim_id"], "APPROVED")
    conn = database.get_connection()
    gap_status = conn.execute(
        "SELECT status FROM gaps WHERE id = 'GAP-ANSWER-OWNER'"
    ).fetchone()[0]
    conn.close()
    assert gap_status == "resolved"
    assert result["source_id"] in {
        source["source_id"] for source in retrieval.get_visible_sources("Incoming", PROJECT_ID)
    }


def test_claim_edits_append_history_and_revoke_approved_incoming_visibility(
    isolated_db: Path,
) -> None:
    _create_project()
    evidence_id = _create_source(
        "SRC-EDIT",
        "edit.txt",
        "public",
        "The synthetic launch owner is Priya Shah.",
    )
    _create_claim(
        "CLM-EDIT",
        [evidence_id],
        review_status="APPROVED",
        claim_text="Launch owner is Priya Shah.",
        claim_type="Owner",
    )
    assert retrieval.get_visible_claims("Incoming", PROJECT_ID)[0]["claim_id"] == "CLM-EDIT"

    assert claim_history.edit_claim(
        "Reviewer",
        "CLM-EDIT",
        "Launch owner is Alex Chen.",
        "The departing teammate corrected the assignment.",
    ) == 1
    assert retrieval.get_visible_claims("Incoming", PROJECT_ID) == []
    assert claim_history.edit_claim(
        "Admin",
        "CLM-EDIT",
        "Launch owner is Alex Chen and the backup is Priya Shah.",
        "Added the agreed backup owner.",
    ) == 2

    history = claim_history.get_claim_history("Reviewer", "CLM-EDIT")
    assert history["current_text"] == "Launch owner is Alex Chen and the backup is Priya Shah."
    assert history["review_status"] == "EDITED_PENDING_REVIEW"
    assert [version["text"] for version in history["versions"]] == [
        "Launch owner is Priya Shah.",
        "Launch owner is Alex Chen.",
    ]
    assert [version["version"] for version in history["versions"]] == [1, 2]
    assert [version["reason"] for version in history["versions"]] == [
        "The departing teammate corrected the assignment.",
        "Added the agreed backup owner.",
    ]

    conn = database.get_connection()
    reviews = conn.execute(
        "SELECT action, comment FROM reviews WHERE claim_id = 'CLM-EDIT' ORDER BY timestamp"
    ).fetchall()
    audit_count = conn.execute(
        "SELECT COUNT(*) FROM audit_logs WHERE target_id = 'CLM-EDIT' AND action = 'EDIT_CLAIM'"
    ).fetchone()[0]
    conn.close()
    assert len(reviews) == 2
    assert all(review["action"] == "EDITED" for review in reviews)
    assert audit_count == 2

    permissions.perform_claim_review("Reviewer", "CLM-EDIT", "APPROVED")
    assert retrieval.get_visible_claims("Incoming", PROJECT_ID)[0]["claim_id"] == "CLM-EDIT"


def test_claim_edits_require_reviewer_and_a_reason(isolated_db: Path) -> None:
    _create_project()
    evidence_id = _create_source("SRC-EDIT-DENIED", "edit-denied.txt", "public", "Evidence")
    _create_claim("CLM-EDIT-DENIED", [evidence_id])

    with pytest.raises(PermissionError):
        claim_history.edit_claim(
            "Incoming",
            "CLM-EDIT-DENIED",
            "Changed claim",
            "A reason",
        )
    with pytest.raises(ValueError, match="reason"):
        claim_history.edit_claim(
            "Reviewer",
            "CLM-EDIT-DENIED",
            "Changed claim",
            " ",
        )
    assert claim_history.get_claim_history("Reviewer", "CLM-EDIT-DENIED")["versions"] == []


def test_handover_release_snapshot_is_immutable_and_public_only(isolated_db: Path) -> None:
    _create_project()
    public = _create_source(
        "SRC-RELEASE-PUBLIC",
        "release-public.txt",
        "public",
        "Public release evidence with alice@example.test",
    )
    restricted = _create_source(
        "SRC-RELEASE-RESTRICTED",
        "release-restricted.txt",
        "restricted",
        "Restricted release evidence",
    )
    _create_claim(
        "CLM-RELEASE-PUBLIC",
        [public],
        review_status="APPROVED",
        claim_text="Public claim for release",
        claim_type="Decision",
    )
    _create_claim(
        "CLM-RELEASE-MIXED",
        [public, restricted],
        review_status="APPROVED",
        claim_text="Claim with restricted citation",
    )
    _create_claim(
        "CLM-RELEASE-PENDING",
        [public],
        claim_text="Pending claim must stay out",
    )

    released = handover_release.release_handover("Reviewer", PROJECT_ID)
    assert released["version"] == 1
    assert [claim["claim_id"] for claim in released["snapshot"]["claims"]] == [
        "CLM-RELEASE-PUBLIC"
    ]
    released_claim = released["snapshot"]["claims"][0]
    assert released_claim["review_status"] == "APPROVED"
    assert released_claim["evidence"][0]["sensitivity"] == "public"
    assert "alice@example.test" not in repr(released["snapshot"])
    snapshot_before = json.dumps(released["snapshot"], sort_keys=True)

    conn = database.get_connection()
    conn.execute(
        "UPDATE claims SET claim_text = 'Changed after release' WHERE claim_id = ?",
        ("CLM-RELEASE-PUBLIC",),
    )
    conn.execute(
        "UPDATE evidence_chunks SET excerpt = 'Changed source after release' WHERE evidence_id = ?",
        (public,),
    )
    conn.commit()
    stored_snapshot = conn.execute(
        "SELECT snapshot_json FROM handover_versions WHERE id = ?",
        (released["id"],),
    ).fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        conn.execute(
            "UPDATE handover_versions SET snapshot_json = '{}' WHERE id = ?",
            (released["id"],),
        )
    conn.rollback()
    conn.close()
    assert stored_snapshot == snapshot_before
    latest = handover_release.get_latest_release("Incoming", PROJECT_ID)
    assert json.dumps(latest["snapshot"], sort_keys=True) == snapshot_before


def test_handover_release_versions_acknowledgement_and_role_checks(isolated_db: Path) -> None:
    _create_project()
    evidence_id = _create_source(
        "SRC-ACK",
        "ack.txt",
        "public",
        "Public handover evidence.",
    )
    _create_claim(
        "CLM-ACK",
        [evidence_id],
        review_status="APPROVED",
        claim_text="A releasable approved claim.",
    )

    with pytest.raises(PermissionError):
        handover_release.release_handover("Incoming", PROJECT_ID)
    with pytest.raises(PermissionError):
        handover_release.acknowledge_latest_release("Reviewer", PROJECT_ID)
    with pytest.raises(ValueError, match="no released handover"):
        handover_release.acknowledge_latest_release("Incoming", PROJECT_ID)

    first_release = handover_release.release_handover("Admin", PROJECT_ID)
    acknowledgement = handover_release.acknowledge_latest_release("Incoming", PROJECT_ID)
    assert acknowledgement["version"] == 1
    assert acknowledgement["user_id"] == "USR-DEMO-INCOMING"
    with pytest.raises(ValueError, match="already acknowledged"):
        handover_release.acknowledge_latest_release("Incoming", PROJECT_ID)

    permissions.perform_claim_review("Reviewer", "CLM-ACK", "REJECTED")
    permissions.perform_claim_review("Reviewer", "CLM-ACK", "APPROVED")
    second_release = handover_release.release_handover("Reviewer", PROJECT_ID)
    assert second_release["version"] == 2
    latest = handover_release.get_latest_release("Incoming", PROJECT_ID)
    assert latest["id"] == second_release["id"]
    assert latest["acknowledgements"] == []
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        conn = database.get_connection()
        try:
            conn.execute(
                "DELETE FROM handover_versions WHERE id = ?",
                (first_release["id"],),
            )
        finally:
            conn.close()
