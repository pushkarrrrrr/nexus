"""NEXUS High-Performance Intelligence & Reasoning Subsystem.

Provides:
- FastPathEngine: Sub-15ms multi-lingual pattern & intent dispatch
- GroundingValidator: Two-pass schema and environmental ground-truth validation
- ScreenPerceptionReasoner: Context-grounded multi-modal screen comprehension
- ContextSynthesizer: Unified cross-memory personalization and context grounding
"""

from packages.shared.nexus_shared.intelligence.context_synthesizer import ContextSynthesizer
from packages.shared.nexus_shared.intelligence.fast_path import FastPathEngine, FastPathMatch
from packages.shared.nexus_shared.intelligence.grounding import (
    GroundingValidator,
    ValidationVerdict,
)
from packages.shared.nexus_shared.intelligence.screen_reasoner import ScreenPerceptionReasoner

__all__ = [
    "ContextSynthesizer",
    "FastPathEngine",
    "FastPathMatch",
    "GroundingValidator",
    "ScreenPerceptionReasoner",
    "ValidationVerdict",
]
