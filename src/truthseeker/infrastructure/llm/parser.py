"""LLM response parsing and validation."""

import json
import logging
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from ...domain.models import AnalysisResult, Reference, Verdict

logger = logging.getLogger(__name__)


def llm_system_prompt() -> str:
    """Return system prompt instructing LLM to emit structured JSON.

    Returns:
        System prompt string for fact-checking analysis.
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


class LLMResponseParser:
    """Parser for LLM responses into validated AnalysisResult objects."""

    @staticmethod
    def _find_first_json(text: str) -> Optional[str]:
        """Find the first JSON object in text.

        Uses json.JSONDecoder().raw_decode for safe parsing of nested structures.

        Args:
            text: Text potentially containing JSON.

        Returns:
            JSON string or None if not found.
        """
        decoder = json.JSONDecoder()
        text_len = len(text)

        for start in range(text_len):
            if text[start] != "{":
                continue
            try:
                _, idx = decoder.raw_decode(text[start:])
                return text[start : start + idx]
            except ValueError:
                continue

        return None

    @staticmethod
    def _normalize_input(data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize JSON data to match AnalysisResult schema.

        Args:
            data: Raw parsed JSON dictionary.

        Returns:
            Normalized dictionary ready for AnalysisResult validation.
        """
        normalized: Dict[str, Any] = {}

        # Verdict normalization
        verdict_raw = data.get("verdict", "")
        if isinstance(verdict_raw, str):
            v = verdict_raw.strip().upper().replace(" ", "_")
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
            for line in raw_refs.splitlines():
                line = line.strip()
                if not line:
                    continue
                if " - " in line:
                    title, url = line.split(" - ", 1)
                elif " | " in line:
                    title, url = line.split(" | ", 1)
                else:
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

    def parse(self, response_text: str) -> AnalysisResult:
        """Parse raw LLM output into validated AnalysisResult.

        Args:
            response_text: Raw text response from LLM.

        Returns:
            Validated AnalysisResult. Returns UNVERIFIABLE verdict if parsing fails.
        """
        logger.debug("LLM full_response (truncated 1000 chars): %s", response_text[:1000])
        json_str = self._find_first_json(response_text)

        if not json_str:
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

        normalized = self._normalize_input(obj)
        logger.debug("Normalized JSON for validation: %s", normalized)

        if not normalized.get("explanation"):
            normalized["explanation"] = "No explanation provided by model."

        # Build Reference objects defensively
        refs = []
        for r in normalized.get("references", []):
            try:
                refs.append(Reference(title=r.get("title", ""), url=r.get("url", "")))
            except Exception as e:
                logger.warning("Skipping invalid reference during parsing: %s — %s", r, e)

        # Validate with Pydantic
        try:
            verdict_value = normalized.get("verdict")
            verdict = (
                Verdict(verdict_value)
                if verdict_value in {v.value for v in Verdict}
                else Verdict.UNVERIFIABLE
            )
            ar = AnalysisResult(
                verdict=verdict,
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


# Convenience function for backward compatibility
def parse_llm_json(response_text: str) -> AnalysisResult:
    """Parse raw LLM output (backward compatibility wrapper).

    Args:
        response_text: Raw text response from LLM.

    Returns:
        Validated AnalysisResult.
    """
    return LLMResponseParser().parse(response_text)

