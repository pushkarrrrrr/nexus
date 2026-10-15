"""Deterministic and pattern-matching Error Classifier for Agent Step Failures."""

import re
from typing import Any, ClassVar

from packages.shared.nexus_shared.agents.recovery.schemas import ErrorCategory


class ErrorClassifier:
    """Classifies execution errors and exceptions into standardized failure categories."""

    POLICY_PATTERNS: ClassVar[list[re.Pattern]] = [
        re.compile(r"policy", re.IGNORECASE),
        re.compile(r"permission\s*denied", re.IGNORECASE),
        re.compile(r"forbidden", re.IGNORECASE),
        re.compile(r"approval\s*required", re.IGNORECASE),
        re.compile(r"blocked\s*by\s*policy", re.IGNORECASE),
    ]

    TIMEOUT_PATTERNS: ClassVar[list[re.Pattern]] = [
        re.compile(r"timed?\s*out", re.IGNORECASE),
        re.compile(r"deadline\s*exceeded", re.IGNORECASE),
        re.compile(r"timeout", re.IGNORECASE),
    ]

    PARAM_PATTERNS: ClassVar[list[re.Pattern]] = [
        re.compile(r"validation\s*error", re.IGNORECASE),
        re.compile(r"missing\s*\d+\s*required", re.IGNORECASE),
        re.compile(r"invalid\s*argument", re.IGNORECASE),
        re.compile(r"unexpected\s*keyword", re.IGNORECASE),
        re.compile(r"value_error", re.IGNORECASE),
        re.compile(r"pydantic", re.IGNORECASE),
    ]

    RESOURCE_NOT_FOUND_PATTERNS: ClassVar[list[re.Pattern]] = [
        re.compile(r"not\s*found", re.IGNORECASE),
        re.compile(r"no\s*such\s*file", re.IGNORECASE),
        re.compile(r"does\s*not\s*exist", re.IGNORECASE),
        re.compile(r"enoent", re.IGNORECASE),
        re.compile(r"404", re.IGNORECASE),
    ]

    ENVIRONMENT_PATTERNS: ClassVar[list[re.Pattern]] = [
        re.compile(r"connection\s*refused", re.IGNORECASE),
        re.compile(r"network\s*unreachable", re.IGNORECASE),
        re.compile(r"read-only\s*file\s*system", re.IGNORECASE),
        re.compile(r"eacces", re.IGNORECASE),
        re.compile(r"oserror", re.IGNORECASE),
    ]

    @classmethod
    def classify(
        cls,
        error_message: str | None,
        exception: Exception | None = None,
        tool_result: dict[str, Any] | None = None,
    ) -> ErrorCategory:
        """Classify failure context into an ErrorCategory."""
        text = str(error_message or "")
        if exception:
            text += f" {type(exception).__name__}: {exception}"
        if tool_result and isinstance(tool_result, dict):
            text += f" {tool_result.get('error') or ''}"

        # 1. Policy Violation check first
        for pat in cls.POLICY_PATTERNS:
            if pat.search(text):
                return "POLICY_REJECTED"

        # 2. Timeout check
        for pat in cls.TIMEOUT_PATTERNS:
            if pat.search(text):
                return "TIMEOUT"

        # 3. Parameter validation check
        for pat in cls.PARAM_PATTERNS:
            if pat.search(text):
                return "PARAM_INVALID"

        # 4. Resource not found check
        for pat in cls.RESOURCE_NOT_FOUND_PATTERNS:
            if pat.search(text):
                return "RESOURCE_NOT_FOUND"

        # 5. Environment / OS check
        for pat in cls.ENVIRONMENT_PATTERNS:
            if pat.search(text):
                return "ENVIRONMENT_ERROR"

        # 6. Tool execution failure
        if text.strip():
            return "TOOL_FAILURE"

        return "UNKNOWN"
