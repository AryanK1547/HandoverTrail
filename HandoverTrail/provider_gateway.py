from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from masking import mask_sensitive_text

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


class RestrictedEvidenceError(PermissionError):
    """Raised when non-public evidence is about to cross a provider boundary."""


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    masked_values: int


def _claims_prompt(evidence_text_block: str) -> str:
    return f"""
You are an expert technical auditor analyzing scattered project files.
Read all evidence excerpts below. Extract a list of unique, deduplicated project claims.
CRITICAL: If multiple excerpts support the SAME claim or decision, combine them into ONE claim and include ALL of their evidence_ids.

EVIDENCE:
{evidence_text_block}

Respond ONLY with a valid JSON object containing a "claims" array. Each array item must have these exact keys:
- "claim_text": string (the consolidated claim)
- "claim_type": string (one of: Decision, Owner, Risk, Dependency, Blocker, Open question, Next action)
- "evidence_ids": array of strings (ALL chunk IDs supporting this specific claim)
"""


def build_provider_payload(chunks: list[Any]) -> dict[str, Any]:
    """Build a provider prompt, refusing every chunk that is not explicitly public."""
    evidence_lines = []
    evidence_ids = set()
    masked_values = 0
    for chunk in chunks:
        if str(chunk["sensitivity"]).strip().lower() != "public":
            raise RestrictedEvidenceError(
                "Only public-sensitivity evidence may be sent to an AI provider."
            )
        excerpt, count = mask_sensitive_text(chunk["excerpt"])
        file_name, filename_count = mask_sensitive_text(chunk["file_name"])
        reference, reference_count = mask_sensitive_text(chunk["reference_location"] or "")
        masked_values += count + filename_count + reference_count
        evidence_ids.add(chunk["evidence_id"])
        evidence_lines.append(
            f"[{chunk['evidence_id']}] Source: {file_name} "
            f"({reference})\nText: {excerpt}\n---"
        )
    return {
        "prompt": _claims_prompt("\n".join(evidence_lines)),
        "evidence_ids": evidence_ids,
        "masked_values": masked_values,
    }


def _invoke_gemini(api_key: str, model: str, prompt: str) -> str:
    if genai is None or types is None:
        raise RuntimeError("The google-genai package is not installed.")
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return response.text


def generate_gemini_response(
    api_key: str, model: str, chunks: list[Any]
) -> ProviderResponse:
    payload = build_provider_payload(chunks)
    text = _invoke_gemini(api_key, model, payload["prompt"])
    return ProviderResponse(text=text, masked_values=payload["masked_values"])


def _invoke_openrouter(api_key: str, model: str, prompt: str) -> str:
    request_body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    request = urllib.request.Request(
        OPENROUTER_API_URL,
        data=request_body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/AryanK1547/HandoverTrail",
            "X-Title": "HandoverTrail",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        try:
            error_payload = json.loads(response_body)
            detail = error_payload.get("error", {}).get("message", response_body)
        except (json.JSONDecodeError, AttributeError):
            detail = response_body
        raise RuntimeError(f"OpenRouter returned HTTP {exc.code}: {detail}") from exc

    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("OpenRouter returned no choices.")
    content = choices[0].get("message", {}).get("content")
    if not isinstance(content, str):
        raise ValueError("OpenRouter returned no text content.")
    return content


def generate_openrouter_response(
    api_key: str, model: str, chunks: list[Any]
) -> ProviderResponse:
    payload = build_provider_payload(chunks)
    text = _invoke_openrouter(api_key, model, payload["prompt"])
    return ProviderResponse(text=text, masked_values=payload["masked_values"])
