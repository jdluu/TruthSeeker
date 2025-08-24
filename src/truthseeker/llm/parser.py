import json
import re
import logging
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from ..models import AnalysisResult, Reference, Verdict

logger = logging.getLogger(__name__)


def llm_system_prompt() -> str:
    """
    Return a system prompt that instructs the LLM to emit a single JSON object
    matching the AnalysisResult schema.

    Consumers should include this prompt as the system message when calling the LLM.
    """
    return """
You are an expert fact-checker. Analyze the user's statement together with provided evidence and return a single valid JSON object (only JSON) that conforms to the following schema:

{
  "verdict": "TRUE|MOSTLY_TRUE|PARTIALLY_TRUE|MOSTLY_FALSE|FALSE|UNVERIFIABLE",
  "explanation": "A detailed explanation with inline citation markers like [1], [2], ...",
  "context": "Optional additional context or nuance",
  "references": [
    { "title": "Source title", "url": "https://..." },
    ...
  ],
  "search_time": 0.0,
  "analysis_time": 0.0
}

- Only return JSON (no surrounding text). If the model includes commentary, ensure the JSON object is still present and valid.
- Use standard HTTP/HTTPS URLs for references.
- Keep values concise where possible but include necessary citations in the explanation field.
"""


def _find_first_json(text: str) -> Optional[str]:
    """
    Attempt to find the first JSON object in a blob of text.

    This implementation looks for the first opening brace '{' and then uses
    json.JSONDecoder().raw_decode to attempt to parse a JSON value starting
    at that position. raw_decode correctly handles nested objects and strings,
    so it's safer and more portable than using PCRE recursion in a regex.
    Returns the matched JSON string or None.
    """
    decoder = json.JSONDecoder()
    text_len = len(text)

    for start in range(text_len):
        if text[start] != "{":
            continue
        try:
            # raw_decode expects a string starting at the JSON value; it returns
            # the parsed object and the number of characters consumed.
            _, idx = decoder.raw_decode(text[start:])
            return text[start : start + idx]
        except ValueError:
            # Not valid JSON at this opening brace; try the next one.
            continue

    return None


def _normalize_input(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize keys and types from the decoded JSON to match AnalysisResult expectations.
    - Map verdict to uppercase and valid enum values where possible.
    - Ensure references is a list of dicts with title/url.
    - Ensure numeric fields are floats.
    """
    normalized: Dict[str, Any] = {}

    # Verdict normalization
    verdict_raw = data.get("verdict", "")
    if isinstance(verdict_raw, str):
        v = verdict_raw.strip().upper().replace(" ", "_")
        # Map common alternatives
        v_map = {
            "MOSTLY TRUE": "MOSTLY_TRUE",
            "PARTIALLY TRUE": "PARTIALLY_TRUE",
            "MOSTLY FALSE": "MOSTLY_FALSE",
            "UNVERIFIABLE": "UNVERIFIABLE",
        }
        v = v_map.get(v, v)
        normalized["verdict"] = v

    # Explanation/context
    normalized["explanation"] = data.get("explanation", "").strip()
    normalized["context"] = data.get("context", None)

    # References - ensure list of dicts with title/url
    refs: List[Dict[str, Any]] = []
    raw_refs = data.get("references", []) or []
    if isinstance(raw_refs, str):
        # If references came as a newline-separated string, attempt to parse lines
        for line in raw_refs.splitlines():
            line = line.strip()
            if not line:
                continue
            if " - " in line:
                title, url = line.split(" - ", 1)
            elif " | " in line:
                title, url = line.split(" | ", 1)
            else:
                # fallback: put the whole line as title, leave url empty
                title, url = line, ""
            refs.append({"title": title.strip(), "url": url.strip()})
    elif isinstance(raw_refs, list):
        for item in raw_refs:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or item.get("source") or item.get("name") or ""
            url = item.get("url") or item.get("link") or ""
            refs.append({"title": title.strip(), "url": url.strip()})
    normalized["references"] = refs

    # Numeric timings
    try:
        normalized["search_time"] = float(data.get("search_time", 0.0) or 0.0)
    except (TypeError, ValueError):
        normalized["search_time"] = 0.0
    try:
        normalized["analysis_time"] = float(data.get("analysis_time", 0.0) or 0.0)
    except (TypeError, ValueError):
        normalized["analysis_time"] = 0.0

    return normalized


def parse_llm_json(response_text: str) -> AnalysisResult:
    """
    Parse raw LLM output and return a validated AnalysisResult.
    If parsing fails, returns an AnalysisResult with verdict UNVERIFIABLE and
    a brief explanation indicating parsing issues.
    """
    # First, try to extract a JSON object
    logger.debug("LLM full_response (truncated 1000 chars): %s", response_text[:1000])
    json_str = _find_first_json(response_text)
    obj: Dict[str, Any]

    if not json_str:
        # Nothing that looks like JSON; attempt to parse line-oriented legacy format
        logger.warning("No JSON found in LLM response; falling back to legacy parsing.")
        return AnalysisResult(
            verdict=Verdict.UNVERIFIABLE,
            explanation="Could not parse model output into structured JSON. Raw output preserved.",
            context=None,
            references=[],
            search_time=0.0,
            analysis_time=0.0,
        )

    try:
        obj = json.loads(json_str)
        logger.debug("Decoded JSON object: %s", obj)
    except json.JSONDecodeError as e:
        logger.warning("JSON decode failed, attempting to sanitize then parse: %s", str(e))
        # Try to fix common issues: replace single quotes with double quotes
        try:
            fixed = json_str.replace("'", '"')
            obj = json.loads(fixed)
            logger.debug("Decoded JSON after fix: %s", obj)
        except Exception as e2:
            logger.exception("Failed to decode JSON from LLM output.")
            return AnalysisResult(
                verdict=Verdict.UNVERIFIABLE,
                explanation="Failed to decode JSON from model output.",
                context=None,
                references=[],
                search_time=0.0,
                analysis_time=0.0,
            )

    normalized = _normalize_input(obj)
    logger.debug("Normalized JSON for validation: %s", normalized)
    # Ensure explanation is non-empty to satisfy Pydantic validator
    if not normalized.get("explanation"):
        normalized["explanation"] = "No explanation provided by model."

    # Build Reference objects defensively to avoid a single bad URL breaking validation
    refs = []
    for r in normalized.get("references", []):
        try:
            refs.append(Reference(title=r.get("title", ""), url=r.get("url", "")))
        except Exception as e:
            logger.warning("Skipping invalid reference during parsing: %s — %s", r, e)

    # Validate with Pydantic AnalysisResult inside try/except to handle any remaining validation issues
    try:
        ar = AnalysisResult(
            verdict=Verdict(normalized.get("verdict")) if normalized.get("verdict") in set(v.value for v in Verdict) else Verdict.UNVERIFIABLE,
            explanation=normalized.get("explanation", ""),
            context=normalized.get("context", None),
            references=refs,
            search_time=normalized.get("search_time", 0.0),
            analysis_time=normalized.get("analysis_time", 0.0),
        )
        return ar
    except ValidationError as ve:
        logger.exception("ValidationError when parsing AnalysisResult: %s", ve.json())
        return AnalysisResult(
            verdict=Verdict.UNVERIFIABLE,
            explanation="Model output could not be validated into the required schema.",
            context=None,
            references=[],
            search_time=0.0,
            analysis_time=0.0,
        )
    except Exception as e:
        logger.exception("Unexpected error when building AnalysisResult: %s", str(e))
        return AnalysisResult(
            verdict=Verdict.UNVERIFIABLE,
            explanation="Unexpected error while parsing model output.",
            context=None,
            references=[],
            search_time=0.0,
            analysis_time=0.0,
        )