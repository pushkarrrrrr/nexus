"""Resource pattern matching and path normalization utilities for Policy and Reversal engines."""

import fnmatch
import os
from pathlib import Path

from packages.shared.nexus_shared.logging import get_logger

logger = get_logger("nexus.policy.utils")


def normalize_resource_target(target: str) -> str:
    """Canonical path normalization to prevent path traversal bypasses (e.g., ../)."""
    target = target.strip()
    if not target:
        return ""
    if target.startswith(("/", "./", "../", "~")) or "/" in target or "\\" in target:
        try:
            expanded = os.path.expanduser(target)
            resolved = Path(expanded).resolve()
            return resolved.as_posix()
        except (ValueError, OSError, RuntimeError):
            return target
    return target


def match_resource_pattern(normalized_target: str, pattern: str) -> bool:
    """Evaluate target against permission resource pattern."""
    pattern = pattern.strip()
    if pattern in ("*", "**"):
        return True
    if normalized_target == pattern:
        return True

    # If pattern is a path pattern, test both raw pattern and resolved pattern
    if "/" in pattern or "\\" in pattern or pattern.startswith(("/", "./", "../", "~")):
        if fnmatch.fnmatch(normalized_target, pattern):
            return True
        try:
            expanded_pat = os.path.expanduser(pattern)
            # If pattern contains wildcards in leaf, resolve base dir
            if "*" in expanded_pat or "?" in expanded_pat:
                # Test direct fnmatch
                if fnmatch.fnmatch(normalized_target, expanded_pat):
                    return True
                # Normalize parent if possible
                prefix = expanded_pat.split("*")[0].split("?")[0]
                if prefix:
                    resolved_prefix = Path(prefix).resolve().as_posix()
                    rest = expanded_pat[len(prefix) :]
                    resolved_pattern = (
                        f"{resolved_prefix.rstrip('/')}/{rest.lstrip('/')}"
                        if rest
                        else resolved_prefix
                    )
                    if fnmatch.fnmatch(normalized_target, resolved_pattern):
                        return True
            else:
                resolved_pat = Path(expanded_pat).resolve().as_posix()
                if fnmatch.fnmatch(normalized_target, resolved_pat):
                    return True
        except (ValueError, OSError, RuntimeError):
            logger.debug("pattern_resolution_failed", pattern=pattern)

    return fnmatch.fnmatch(normalized_target, pattern)
