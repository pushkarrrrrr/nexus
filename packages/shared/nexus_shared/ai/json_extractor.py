"""Robust JSON Extractor for Model Responses.

Extracts valid JSON payloads from free-form text, markdown codeblocks,
and conversational preamble/postscript produced by LLMs.
"""

import json
import re


def extract_json_from_text(raw_text: str) -> str:
    """Extract clean JSON substring from arbitrary LLM output.

    Handles:
    1. Direct JSON objects and arrays.
    2. Markdown fenced codeblocks: ```json ... ``` or ``` ... ```.
    3. Conversational preamble (e.g., 'Sure, here is the JSON:').
    4. Postscript notes and trailing explanations.

    Returns:
        Extracted JSON substring ready for Pydantic validation.
    """
    text = raw_text.strip()
    if not text:
        return text

    # 1. Check if the text is directly valid JSON
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # 2. Look for markdown code fence with json or generic
    fenced_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if fenced_match:
        candidate = fenced_match.group(1).strip()
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            # Continue to outermost brace inspection
            text = candidate

    # 3. Look for outermost balanced { ... } object
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = text[first_brace : last_brace + 1].strip()
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    # 4. Look for outermost balanced [ ... ] array
    first_bracket = text.find("[")
    last_bracket = text.rfind("]")
    if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
        candidate = text[first_bracket : last_bracket + 1].strip()
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    # 5. Fallback: strip any outer code fence
    cleaned = re.sub(r"^```(?:json)?\s*", "", text)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()
