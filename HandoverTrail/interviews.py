from __future__ import annotations

import uuid
from datetime import datetime

from conflict_detection import detect_project_conflicts
from database import get_connection
from permissions import (
    can_review,
    normalize_role,
    require_departing_role,
    require_role,
)

DEPARTING_USER_ID = "USR-DEMO-DEPARTING"

_QUESTION_TEMPLATES = {
    "task_without_owner": "Who will own {subject}, and where should that ownership be recorded?",
    "decision_missing_date": "When was {subject} decided? Please provide the date or a source that records it.",
    "decision_missing_rationale": "Why was {subject} decided? Please share the rationale or supporting source.",
    "risk_missing_mitigation": "What mitigation or fallback is planned for {subject}?",
    "single_source_claim": "Can you confirm {subject} and point to another source that supports it?",
}


def _reviewer_id(conn, role: str) -> str:
    require_role(role, "manage exit-interview questions")
    row = conn.execute(
        "SELECT user_id FROM users WHERE lower(role) = lower(?) ORDER BY user_id LIMIT 1",
        (normalize_role(role),),
    ).fetchone()
    if not row:
        raise PermissionError("No demo reviewer is configured for the selected role.")
    return row["user_id"]


def _departing_id(conn, role: str) -> str:
    user_id = require_departing_role(role, "view or answer assigned questions")
    row = conn.execute(
        """
        SELECT user_id FROM user_role_assignments
        WHERE user_id = ? AND role = 'Departing'
        """,
        (user_id,),
    ).fetchone()
    if not row:
        raise PermissionError("No demo Departing identity is configured.")
    return user_id


def _audit(conn, actor_id: str, action: str, target_type: str, target_id: str, now: str) -> None:
    conn.execute(
        """
        INSERT INTO audit_logs (log_id, actor_id, action, target_type, target_id, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            f"AUD-{uuid.uuid4().hex[:12].upper()}",
            actor_id,
            action,
            target_type,
            target_id,
            now,
        ),
    )


def generate_questions(role: str, project_id: str) -> int:
    detect_project_conflicts(role, project_id)
    conn = get_connection()
    try:
        reviewer_id = _reviewer_id(conn, role)
        now = datetime.now().isoformat()
        gaps = conn.execute(
            """
            SELECT g.id, g.gap_type, g.subject
            FROM gaps g
            WHERE g.project_id = ? AND g.status = 'open'
              AND NOT EXISTS (SELECT 1 FROM questions q WHERE q.gap_id = g.id)
            ORDER BY g.created_at, g.id
            """,
            (project_id,),
        ).fetchall()
        created = 0
        for gap in gaps:
            template = _QUESTION_TEMPLATES.get(gap["gap_type"])
            if not template:
                continue
            question_id = f"Q-{uuid.uuid4().hex[:12].upper()}"
            question_text = template.format(subject=gap["subject"] or "this project detail")
            conn.execute(
                """
                INSERT INTO questions
                    (id, gap_id, text, status, assigned_role, assigned_user_id, created_by, created_at)
                VALUES (?, ?, ?, 'DRAFT', 'Departing', ?, ?, ?)
                """,
                (question_id, gap["id"], question_text, DEPARTING_USER_ID, reviewer_id, now),
            )
            _audit(conn, reviewer_id, "GENERATE_INTERVIEW_QUESTION", "question", question_id, now)
            created += 1
        conn.commit()
        return created
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def add_question(role: str, project_id: str, gap_id: str, text: str) -> str:
    question_text = text.strip()
    if not question_text:
        raise ValueError("Enter a question before adding it.")
    conn = get_connection()
    try:
        reviewer_id = _reviewer_id(conn, role)
        gap = conn.execute(
            "SELECT id FROM gaps WHERE id = ? AND project_id = ? AND status = 'open'",
            (gap_id, project_id),
        ).fetchone()
        if not gap:
            raise ValueError("Choose an open evidence gap for this question.")
        question_id = f"Q-{uuid.uuid4().hex[:12].upper()}"
        now = datetime.now().isoformat()
        conn.execute(
            """
            INSERT INTO questions
                (id, gap_id, text, status, assigned_role, assigned_user_id, created_by, created_at)
            VALUES (?, ?, ?, 'DRAFT', 'Departing', ?, ?, ?)
            """,
            (question_id, gap_id, question_text, DEPARTING_USER_ID, reviewer_id, now),
        )
        _audit(conn, reviewer_id, "ADD_INTERVIEW_QUESTION", "question", question_id, now)
        conn.commit()
        return question_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_questions(role: str, project_id: str) -> list[dict]:
    conn = get_connection()
    try:
        if can_review(role):
            rows = conn.execute(
                """
                SELECT q.id, q.gap_id, q.text, q.status, q.assigned_role,
                       q.assigned_user_id, q.created_at, g.gap_type, g.subject
                FROM questions q
                JOIN gaps g ON g.id = q.gap_id
                WHERE g.project_id = ?
                ORDER BY q.created_at, q.id
                """,
                (project_id,),
            ).fetchall()
        else:
            departing_id = _departing_id(conn, role)
            rows = conn.execute(
                """
                SELECT q.id, q.gap_id, q.text, q.status, q.assigned_role,
                       q.assigned_user_id, q.created_at, g.gap_type, g.subject
                FROM questions q
                JOIN gaps g ON g.id = q.gap_id
                WHERE g.project_id = ? AND q.assigned_user_id = ?
                  AND q.status IN ('SENT', 'ANSWERED')
                ORDER BY q.created_at, q.id
                """,
                (project_id, departing_id),
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def update_question(role: str, question_id: str, text: str) -> None:
    question_text = text.strip()
    if not question_text:
        raise ValueError("Question text cannot be empty.")
    conn = get_connection()
    try:
        reviewer_id = _reviewer_id(conn, role)
        question = conn.execute(
            "SELECT status FROM questions WHERE id = ?",
            (question_id,),
        ).fetchone()
        if not question or question["status"] != "DRAFT":
            raise ValueError("Only a draft question can be edited.")
        now = datetime.now().isoformat()
        conn.execute(
            "UPDATE questions SET text = ? WHERE id = ?",
            (question_text, question_id),
        )
        _audit(conn, reviewer_id, "EDIT_INTERVIEW_QUESTION", "question", question_id, now)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_question(role: str, question_id: str) -> None:
    conn = get_connection()
    try:
        reviewer_id = _reviewer_id(conn, role)
        question = conn.execute(
            "SELECT status FROM questions WHERE id = ?",
            (question_id,),
        ).fetchone()
        if not question or question["status"] != "DRAFT":
            raise ValueError("Only a draft question can be deleted.")
        now = datetime.now().isoformat()
        _audit(conn, reviewer_id, "DELETE_INTERVIEW_QUESTION", "question", question_id, now)
        conn.execute("DELETE FROM questions WHERE id = ?", (question_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def send_questions(role: str, project_id: str) -> int:
    conn = get_connection()
    try:
        reviewer_id = _reviewer_id(conn, role)
        questions = conn.execute(
            """
            SELECT q.id FROM questions q
            JOIN gaps g ON g.id = q.gap_id
            WHERE g.project_id = ? AND q.status = 'DRAFT'
              AND q.assigned_user_id = ?
            """,
            (project_id, DEPARTING_USER_ID),
        ).fetchall()
        now = datetime.now().isoformat()
        for question in questions:
            conn.execute(
                "UPDATE questions SET status = 'SENT' WHERE id = ?",
                (question["id"],),
            )
            _audit(
                conn,
                reviewer_id,
                "SEND_INTERVIEW_QUESTION",
                "question",
                question["id"],
                now,
            )
        conn.commit()
        return len(questions)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_answers(role: str, question_id: str) -> list[dict]:
    conn = get_connection()
    try:
        _reviewer_id(conn, role)
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT a.id, a.text, a.author_id, a.source_id, a.created_at, u.name AS author_name
                FROM answers a
                JOIN users u ON u.user_id = a.author_id
                WHERE a.question_id = ?
                ORDER BY a.created_at
                """,
                (question_id,),
            )
        ]
    finally:
        conn.close()


def submit_answer(
    role: str,
    question_id: str,
    text: str,
    sensitivity: str = "restricted",
) -> dict:
    answer_text = text.strip()
    if not answer_text:
        raise ValueError("Enter an answer before submitting.")
    if sensitivity not in {"public", "restricted"}:
        raise ValueError("Choose public or restricted sensitivity.")
    conn = get_connection()
    try:
        departing_id = _departing_id(conn, role)
        question = conn.execute(
            """
            SELECT q.id, q.text, q.gap_id, q.status, g.project_id
            FROM questions q JOIN gaps g ON g.id = q.gap_id
            WHERE q.id = ? AND q.assigned_user_id = ?
            """,
            (question_id, departing_id),
        ).fetchone()
        if not question or question["status"] != "SENT":
            raise ValueError("This question is unavailable or has already been answered.")
        project_id = question["project_id"]
    finally:
        conn.close()

    import extractor
    import source_parser

    source_id = f"SRC-{uuid.uuid4().hex[:12].upper()}"
    answer_id = f"ANS-{uuid.uuid4().hex[:12].upper()}"
    file_name = f"interview_{source_id}.txt"
    now = datetime.now().isoformat()
    source_text = (
        f"Question: {question['text']}\n"
        f"Answer: {answer_text}\n"
        f"Author: Demo Departing\n"
        f"Timestamp: {now}\n"
    )
    saved_path, _ = source_parser.persist_uploaded_file(
        project_id,
        file_name,
        source_text.encode("utf-8"),
    )

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO sources
                (source_id, project_id, file_name, file_type, uploaded_at, sensitivity, source_type)
            VALUES (?, ?, ?, 'TXT', ?, ?, 'interview')
            """,
            (source_id, project_id, file_name, now, sensitivity),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        saved_path.unlink(missing_ok=True)
        raise
    finally:
        conn.close()

    try:
        source_parser.parse_and_store_sources(project_id, source_ids=[source_id])
        extraction = extractor.extract_claims_from_evidence(
            project_id,
            source_ids=[source_id],
        )
        if extraction.get("status") != "success":
            raise RuntimeError(
                extraction.get("message", "The interview source could not be processed.")
            )
        if extraction["claims_created"] == 0:
            fallback_conn = get_connection()
            try:
                evidence_ids = [
                    row["evidence_id"]
                    for row in fallback_conn.execute(
                        "SELECT evidence_id FROM evidence_chunks WHERE source_id = ?",
                        (source_id,),
                    )
                ]
                claim_id = f"CLM-{uuid.uuid4().hex[:12].upper()}"
                fallback_conn.execute(
                    """
                    INSERT INTO claims
                        (claim_id, project_id, claim_text, claim_type, trust_status, claim_source,
                         review_status, created_at, updated_at)
                    VALUES (?, ?, ?, 'Open question', 'SINGLE_SOURCE',
                            'Interview answer (verbatim)', 'PENDING', ?, ?)
                    """,
                    (
                        claim_id,
                        project_id,
                        f"Interview answer: {answer_text}",
                        now,
                        now,
                    ),
                )
                fallback_conn.executemany(
                    "INSERT INTO claim_evidence (claim_id, evidence_id) VALUES (?, ?)",
                    [(claim_id, evidence_id) for evidence_id in evidence_ids],
                )
                fallback_conn.commit()
                extraction["claims_created"] = 1
                extraction["method"] = "Interview answer (verbatim)"
            except Exception:
                fallback_conn.rollback()
                raise
            finally:
                fallback_conn.close()
    except Exception:
        cleanup = get_connection()
        try:
            cleanup.execute(
                """
                DELETE FROM claims
                WHERE claim_id IN (
                    SELECT ce.claim_id FROM claim_evidence ce
                    JOIN evidence_chunks e ON e.evidence_id = ce.evidence_id
                    WHERE e.source_id = ?
                )
                """,
                (source_id,),
            )
            cleanup.execute("DELETE FROM sources WHERE source_id = ?", (source_id,))
            cleanup.commit()
        finally:
            cleanup.close()
            saved_path.unlink(missing_ok=True)
        raise

    conn = get_connection()
    try:
        latest_question = conn.execute(
            """
            SELECT status FROM questions
            WHERE id = ? AND assigned_user_id = ?
            """,
            (question_id, departing_id),
        ).fetchone()
        if not latest_question or latest_question["status"] != "SENT":
            raise ValueError("This question was answered in another session.")
        conn.execute(
            """
            INSERT INTO answers (id, question_id, text, author_id, source_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (answer_id, question_id, answer_text, departing_id, source_id, now),
        )
        conn.execute(
            "UPDATE questions SET status = 'ANSWERED' WHERE id = ?",
            (question_id,),
        )
        conn.execute(
            """
            UPDATE gaps SET status = 'answered-pending-review'
            WHERE id = ? AND status = 'open'
            """,
            (question["gap_id"],),
        )
        _audit(
            conn,
            departing_id,
            "SUBMIT_INTERVIEW_ANSWER",
            "answer",
            answer_id,
            now,
        )
        conn.commit()
        return {
            "answer_id": answer_id,
            "source_id": source_id,
            "claims_created": extraction["claims_created"],
            "method": extraction["method"],
            "sensitivity": sensitivity,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
