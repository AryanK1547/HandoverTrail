import hashlib
import json
import os
import re
import uuid
from datetime import datetime
from typing import Callable, Iterable
from database import get_connection
from provider_gateway import (
    build_provider_payload,
    generate_gemini_response,
    generate_openrouter_response,
)

GEMINI_MODEL = "gemini-3.6-flash"
OPENROUTER_MODEL = "deepseek/deepseek-v4.1-flash-1017"


def _normalize_claim_text(value: str) -> str:
    text = re.sub(r"^\s*```(?:markdown|md)?\s*", "", value, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    text = re.sub(r"^\s*#{1,6}\s*", "", text)
    text = re.sub(r"^\s*[-*+]\s+", "", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", text)
    text = text.replace("`", "")
    return " ".join(text.split()).strip()


def _extraction_key(
    project_id: str,
    claim_text: str,
    claim_type: str,
    evidence_ids: set[str],
) -> str:
    stable_content = json.dumps(
        [
            project_id,
            _normalize_claim_text(claim_text).casefold(),
            claim_type,
            sorted(evidence_ids),
        ],
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(stable_content.encode("utf-8")).hexdigest()


def _record_extraction_run(
    conn,
    project_id: str,
    status: str,
    method: str,
    claims_created: int,
    fallback_reason: str | None,
    masked_values: int,
    source_ids: Iterable[str],
) -> None:
    conn.execute(
        """
        INSERT INTO extraction_runs
            (run_id, project_id, status, method, claims_created, fallback_reason,
             masked_values, source_ids_json, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"EXR-{uuid.uuid4().hex[:12].upper()}",
            project_id,
            status,
            method,
            claims_created,
            fallback_reason,
            masked_values,
            json.dumps(sorted(set(source_ids))),
            datetime.now().isoformat(),
        ),
    )


def get_latest_extraction_run(project_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT status, method, claims_created, fallback_reason, masked_values,
                   source_ids_json, completed_at
            FROM extraction_runs
            WHERE project_id = ?
            ORDER BY completed_at DESC, run_id DESC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["source_ids"] = json.loads(result.pop("source_ids_json"))
        result["project_id"] = project_id
        return result
    finally:
        conn.close()


def _parse_claims(response_text: str, valid_evidence_ids: set) -> dict:
    if not response_text:
        raise ValueError("The provider returned an empty response.")

    clean_json = response_text.strip()
    clean_json = re.sub(r"^```(?:json)?\s*", "", clean_json, flags=re.IGNORECASE)
    clean_json = re.sub(r"\s*```$", "", clean_json)

    extracted = json.loads(clean_json)
    if isinstance(extracted, dict):
        extracted = extracted.get("claims")
    if not isinstance(extracted, list):
        raise ValueError('The provider response did not contain a "claims" array.')

    valid_claim_types = {
        "Decision", "Owner", "Risk", "Dependency", "Blocker", "Open question", "Next action"
    }
    claims = {}
    for item in extracted:
        if not isinstance(item, dict):
            raise ValueError("The provider returned a claim that was not a JSON object.")

        claim_text = item.get("claim_text")
        claim_type = item.get("claim_type", "Decision")
        evidence_ids = item.get("evidence_ids")
        if not isinstance(claim_text, str) or not _normalize_claim_text(claim_text):
            raise ValueError("The provider returned a claim without valid claim_text.")
        claim_text = _normalize_claim_text(claim_text)
        if claim_type not in valid_claim_types:
            raise ValueError(f"The provider returned an invalid claim_type for claim: {claim_text}.")
        if not isinstance(evidence_ids, list) or not all(
            isinstance(evidence_id, str) for evidence_id in evidence_ids
        ):
            raise ValueError(f"The provider returned invalid evidence_ids for claim: {claim_text}.")
        if not set(evidence_ids).issubset(valid_evidence_ids):
            raise ValueError(f"The provider returned unknown evidence_ids for claim: {claim_text}.")

        claims[claim_text] = {
            "claim_type": claim_type,
            "evidence_ids": set(evidence_ids),
        }
    return claims


def _label_claims(claims: dict, method: str) -> dict:
    return {
        claim_text: {**claim, "claim_source": method}
        for claim_text, claim in claims.items()
    }


def _merge_claims(target: dict, additions: dict) -> None:
    for claim_text, claim in additions.items():
        if claim_text not in target:
            target[claim_text] = claim
            continue
        existing = target[claim_text]
        existing["evidence_ids"].update(claim["evidence_ids"])
        methods = set(existing["claim_source"].split(" + "))
        methods.update(claim["claim_source"].split(" + "))
        existing["claim_source"] = " + ".join(sorted(methods))


def _heuristic_claims(chunks: list, method: str) -> dict:
    rules = (
        (
            "Decision",
            re.compile(
                r"\b(?:decisions?|decid\w*|confirm\w*|select\w*|chose|chosen|"
                r"approved|will use|will adopt)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "Owner",
            re.compile(
                r"\b(?:owner\s*(?:is|:|=)|assigned to|responsible for|owns?|"
                r"takes ownership of)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "Blocker",
            re.compile(
                r"\b(?:blocked|blocker|blocking|cannot proceed|unable to proceed)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "Risk",
            re.compile(
                r"\b(?:risk|may fail|might fail|could fail|failure mode)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "Dependency",
            re.compile(
                r"\b(?:depends? on|dependent on|dependencies?)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "Next action",
            re.compile(
                r"\b(?:next step|next action|action item|to-?do|pending action)\b",
                re.IGNORECASE,
            ),
        ),
    )
    claims = {}
    claim_keys = {}
    for chunk in chunks:
        statements = re.split(r"(?<=[.!?;])\s+|\r?\n+", chunk["excerpt"])
        for raw_statement in statements:
            if raw_statement.strip().endswith("?"):
                continue
            claim_text = _normalize_claim_text(raw_statement)
            if not claim_text:
                continue
            claim_type = next(
                (
                    candidate_type
                    for candidate_type, pattern in rules
                    if pattern.search(claim_text)
                ),
                None,
            )
            if claim_type is None:
                continue

            key = claim_text.casefold()
            existing = claim_keys.get(key)
            if existing is None:
                claims[claim_text] = {
                    "claim_type": claim_type,
                    "evidence_ids": {chunk["evidence_id"]},
                    "claim_source": method,
                }
                claim_keys[key] = claim_text
            else:
                claims[existing]["evidence_ids"].add(chunk["evidence_id"])
    return claims


def extract_claims_from_evidence(
    project_id: str = "PROJ-DEMO-001",
    api_key: str = None,
    openrouter_api_key: str = None,
    progress_callback: Callable[[int, str], None] | None = None,
    source_ids: Iterable[str] | None = None,
) -> dict:
    def report_progress(value: int, message: str) -> None:
        if progress_callback:
            progress_callback(value, message)

    report_progress(5, "Loading stored evidence...")
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT e.evidence_id, e.source_id, e.excerpt, e.reference_location,
               s.file_name, s.sensitivity
        FROM evidence_chunks e
        JOIN sources s ON e.source_id = s.source_id
        WHERE s.project_id = ?
    """
    params: list[str] = [project_id]
    selected_source_ids = list(dict.fromkeys(source_ids)) if source_ids is not None else None
    if selected_source_ids is not None:
        if not selected_source_ids:
            conn.close()
            return {
                "status": "error",
                "message": "Select at least one source for scoped claim extraction.",
            }
        placeholders = ",".join("?" for _ in selected_source_ids)
        query += f" AND s.source_id IN ({placeholders})"
        params.extend(selected_source_ids)
    cursor.execute(query, params)
    chunks = cursor.fetchall()

    if not chunks:
        report_progress(100, "No evidence found. Parse source files before extracting claims.")
        _record_extraction_run(
            conn,
            project_id,
            "error",
            "Not run",
            0,
            "No evidence chunks found. Parse files before extracting claims.",
            0,
            selected_source_ids or (),
        )
        conn.commit()
        conn.close()
        return {"status": "error", "message": "No evidence chunks found for extraction. Please parse files first."}

    public_chunks = [chunk for chunk in chunks if chunk["sensitivity"] == "public"]
    restricted_chunks = [chunk for chunk in chunks if chunk["sensitivity"] != "public"]
    claims_dict = {}
    extraction_method = "Universal Heuristic Fallback"
    provider_note = None
    gemini_error = None
    provider_succeeded = False
    providers_disabled = os.environ.get("HANDOVERTRAIL_DISABLE_PROVIDERS", "").casefold() in {
        "1",
        "true",
        "yes",
    }
    public_evidence_ids = {chunk["evidence_id"] for chunk in public_chunks}
    provider_payload_error = None
    masked_values = 0
    if public_chunks and any(key and key.strip() for key in (api_key, openrouter_api_key)):
        try:
            masked_values = build_provider_payload(public_chunks)["masked_values"]
        except ValueError as exc:
            provider_payload_error = str(exc)
    report_progress(
        15,
        f"Loaded {len(chunks)} evidence chunks; only {len(public_chunks)} public chunks may go to providers.",
    )

    # --- PATH A: LIVE GEMINI EXTRACTION (AI-Driven Deduplication) ---
    if not public_chunks:
        gemini_error = "No public evidence is available for provider extraction."
        report_progress(35, gemini_error)
    elif providers_disabled:
        gemini_error = "Provider calls are disabled for this app run."
        report_progress(35, gemini_error)
    elif provider_payload_error:
        gemini_error = provider_payload_error
        report_progress(35, f"Provider extraction skipped: {gemini_error}")
    elif not api_key or not api_key.strip():
        gemini_error = "GEMINI_API_KEY is not configured in Streamlit secrets."
        report_progress(35, f"Gemini skipped: {gemini_error}")
    else:
        try:
            report_progress(30, f"Sending evidence to Gemini ({GEMINI_MODEL})...")
            response = generate_gemini_response(
                api_key=api_key.strip(),
                model=GEMINI_MODEL,
                chunks=public_chunks,
            )
            claims_dict = _label_claims(
                _parse_claims(response.text, public_evidence_ids),
                "Gemini API",
            )
            extraction_method = "Gemini API"
            provider_succeeded = True
            report_progress(70, "Gemini responded. Validating its claims...")
        except Exception as exc:
            error_message = str(exc)
            for secret in (api_key, openrouter_api_key):
                if secret:
                    error_message = error_message.replace(secret, "[redacted]")
            gemini_error = f"Gemini failed ({type(exc).__name__}): {error_message}"
            claims_dict = {}
            report_progress(42, f"{gemini_error} Trying OpenRouter...")

    # --- PATH B: OPENROUTER FALLBACK ---
    openrouter_error = None
    if not provider_succeeded:
        if not public_chunks:
            openrouter_error = "OpenRouter skipped because no public evidence is available."
            report_progress(62, openrouter_error)
        elif providers_disabled:
            openrouter_error = "OpenRouter skipped because provider calls are disabled."
            report_progress(62, openrouter_error)
        elif provider_payload_error:
            openrouter_error = f"OpenRouter skipped: {provider_payload_error}"
            report_progress(62, openrouter_error)
        elif not openrouter_api_key or not openrouter_api_key.strip():
            openrouter_error = "OPENROUTER_API_KEY is not configured in Streamlit secrets."
            report_progress(62, f"OpenRouter skipped: {openrouter_error}")
        else:
            try:
                report_progress(58, f"Sending evidence to OpenRouter ({OPENROUTER_MODEL})...")
                response = generate_openrouter_response(
                    api_key=openrouter_api_key.strip(),
                    model=OPENROUTER_MODEL,
                    chunks=public_chunks,
                )
                claims_dict = _label_claims(
                    _parse_claims(response.text, public_evidence_ids),
                    "OpenRouter API",
                )
                extraction_method = "OpenRouter API"
                provider_succeeded = True
                report_progress(78, "OpenRouter responded. Validating its claims...")
            except Exception as exc:
                error_message = str(exc)
                for secret in (api_key, openrouter_api_key):
                    if secret:
                        error_message = error_message.replace(secret, "[redacted]")
                openrouter_error = f"OpenRouter failed ({type(exc).__name__}): {error_message}"
                claims_dict = {}
                report_progress(72, f"{openrouter_error} Switching to local keyword fallback...")

    if not provider_succeeded:
        extraction_method = "Universal Keyword Fallback"
        provider_note = " ".join(
            reason for reason in (gemini_error, openrouter_error) if reason
        )
        report_progress(78, "Using local universal keyword fallback...")
        _merge_claims(
            claims_dict,
            _heuristic_claims(chunks, "Universal Keyword Fallback"),
        )
    else:
        if extraction_method == "OpenRouter API":
            provider_note = f"{gemini_error} OpenRouter handled extraction."
        if restricted_chunks:
            _merge_claims(
                claims_dict,
                _heuristic_claims(
                    restricted_chunks,
                    "Local heuristic (restricted sources)",
                ),
            )
            extraction_method += " + local restricted-source heuristic"
            report_progress(78, "Using local heuristic for restricted-source evidence...")

    report_progress(88, f"Saving {len(claims_dict)} extracted claims...")

    created_count = 0
    now = datetime.now().isoformat()

    for text, data in claims_dict.items():
        text = _normalize_claim_text(text)
        if not data["evidence_ids"]:
            continue

        extraction_key = _extraction_key(
            project_id,
            text,
            data["claim_type"],
            data["evidence_ids"],
        )
        claim_id = f"CLM-{uuid.uuid4().hex[:8].upper()}"
        cursor.execute("""
            INSERT OR IGNORE INTO claims
                (claim_id, project_id, claim_text, claim_type, trust_status, claim_source,
                 review_status, extraction_key, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                claim_id,
                project_id,
                text,
                data["claim_type"],
                "SINGLE_SOURCE",
                data["claim_source"],
                "PENDING",
                extraction_key,
                now,
                now,
            ))
        if cursor.rowcount == 0:
            continue

        for evd_id in data["evidence_ids"]:
            cursor.execute("""
                INSERT OR IGNORE INTO claim_evidence (claim_id, evidence_id)
                VALUES (?, ?)
            """, (claim_id, evd_id))
        created_count += 1

    run_source_ids = (
        selected_source_ids
        if selected_source_ids is not None
        else {chunk["source_id"] for chunk in chunks}
    )
    _record_extraction_run(
        conn,
        project_id,
        "success",
        extraction_method,
        created_count,
        provider_note,
        masked_values,
        run_source_ids,
    )
    conn.commit()
    conn.close()
    report_progress(100, f"Finished: {created_count} claims created using {extraction_method}.")

    return {
        "status": "success",
        "claims_created": created_count,
        "method": extraction_method,
        "fallback_reason": provider_note,
        "masked_values": masked_values,
    }


if __name__ == "__main__":
    result = extract_claims_from_evidence()
    print("Extraction Result:", result)