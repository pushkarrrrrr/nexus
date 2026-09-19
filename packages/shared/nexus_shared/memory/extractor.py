"""Intelligent Memory Extractor & Relevance Filter.

Analyzes conversational turns and session transcripts to identify durable,
high-value memories (preferences, operational facts, procedures, episodic milestones)
while strictly discarding ephemeral noise (greetings, acknowledgments, chatter).
"""

import re

from packages.types.nexus_types.schemas import MemoryClass, MemoryCreate

# Patterns indicative of conversational noise to reject
NOISE_PATTERNS = [
    r"^(hi|hello|hey|good\s+(morning|afternoon|evening)|howdy)\b",
    r"^(thanks|thank\s+you|thx|cheers|appreciated|great|awesome|cool|ok|okay|got\s+it)\b",
    r"^(yes|no|yep|nope|sure|definitely|absolutely)\b",
    r"^(what('s|\s+is)\s+the\s+weather|tell\s+me\s+a\s+joke)\b",
    r"^(bye|goodbye|see\s+you|cya)\b",
]

# Patterns signaling explicit user preferences or durable knowledge
SEMANTIC_PATTERNS = [
    (r"(?:i\s+prefer|i\s+like|i\s+want|my\s+preference\s+is)\s+(.+)", "User Preference: {}"),
    (r"(?:i\s+am|my\s+name\s+is|i\s+work\s+as|my\s+role\s+is)\s+(.+)", "User Profile Fact: {}"),
    (r"(?:always|never)\s+(?:use|format|create|run)\s+(.+)", "User Directive: {}"),
    (r"(?:note\s+that|remember\s+that|fact:)\s+(.+)", "Domain Fact: {}"),
]

PROCEDURAL_PATTERNS = [
    (r"(?:how\s+to|steps?\s+to|to\s+deploy|to\s+build|to\s+run)\s+(.+)", "Procedure: {}"),
    (r"(?:first|step\s+1),?\s+(.+)", "Workflow Sequence: {}"),
]

EPISODIC_PATTERNS = [
    (
        r"(?:fixed|resolved|completed|encountered\s+error|failed\s+on)\s+(.+)",
        "Execution Outcome: {}",
    ),
]


class MemoryExtractor:
    """Evaluates conversation turns and extracts candidate memories."""

    def is_noise(self, text: str) -> bool:
        """Return True if text is trivial conversational chatter."""
        clean = text.strip().lower()
        if len(clean) < 8:
            return True
        for pattern in NOISE_PATTERNS:
            if re.search(pattern, clean, re.IGNORECASE) and len(clean.split()) <= 6:
                return True
        return False

    def extract_from_turns(
        self,
        messages: list[dict[str, str]],
        session_id: str | None = None,
    ) -> list[MemoryCreate]:
        """Extract high-value memories from a series of dialogue turns."""
        extracted: list[MemoryCreate] = []

        for msg in messages:
            content = msg.get("content", "").strip()
            role = msg.get("role", "user").lower()

            # Skip noise or empty messages
            if self.is_noise(content):
                continue

            # 1. Check for procedural patterns
            matched_proc = False
            for pattern, title_fmt in PROCEDURAL_PATTERNS:
                m = re.search(pattern, content, re.IGNORECASE)
                if m:
                    title = title_fmt.format(m.group(1)[:50].strip())
                    extracted.append(
                        MemoryCreate(
                            title=title,
                            content=content,
                            memory_class=MemoryClass.PROCEDURAL,
                            source_session_id=session_id,
                            confidence=0.9,
                            tags=["procedural", "workflow"],
                        )
                    )
                    matched_proc = True
                    break
            if matched_proc:
                continue

            # 2. Check for episodic execution patterns (often from assistant or system)
            matched_epi = False
            for pattern, title_fmt in EPISODIC_PATTERNS:
                m = re.search(pattern, content, re.IGNORECASE)
                if m:
                    title = title_fmt.format(m.group(1)[:50].strip())
                    extracted.append(
                        MemoryCreate(
                            title=title,
                            content=content,
                            memory_class=MemoryClass.EPISODIC,
                            source_session_id=session_id,
                            confidence=0.85,
                            tags=["episodic", "execution"],
                        )
                    )
                    matched_epi = True
                    break
            if matched_epi:
                continue

            # 3. Check for semantic preference / factual patterns
            matched_sem = False
            for pattern, title_fmt in SEMANTIC_PATTERNS:
                m = re.search(pattern, content, re.IGNORECASE)
                if m:
                    title = title_fmt.format(m.group(1)[:50].strip())
                    extracted.append(
                        MemoryCreate(
                            title=title,
                            content=content,
                            memory_class=MemoryClass.SEMANTIC,
                            source_session_id=session_id,
                            confidence=0.95,
                            tags=["semantic", "user_preference" if role == "user" else "fact"],
                        )
                    )
                    matched_sem = True
                    break
            if matched_sem:
                continue

            # 4. If substantive user statement (>= 15 words) with clear context, capture as conversational memory
            words = content.split()
            if len(words) >= 15 and role == "user":
                summary_title = f"Context: {' '.join(words[:6])}..."
                extracted.append(
                    MemoryCreate(
                        title=summary_title,
                        content=content,
                        memory_class=MemoryClass.CONVERSATIONAL,
                        source_session_id=session_id,
                        confidence=0.75,
                        tags=["conversational"],
                    )
                )

        return extracted
