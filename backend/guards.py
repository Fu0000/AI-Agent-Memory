"""
Tool-Level Hard Constraints — Code-enforced rules replacing System Prompt text.

These guards ensure data quality regardless of which AI model or client
is calling the MCP tools. Rules that can be expressed in code should be
enforced in code, not hoped-for via prompt instructions.

Refs: OPT-6.1
"""

import re
from typing import Optional, Set


# =========================================================================
# Read-before-write guard
# =========================================================================

class ReadTracker:
    """Tracks which URIs have been recently read.

    Prevents blind updates to memories the AI hasn't reviewed first.
    """

    def __init__(self, max_size: int = 100):
        self._read_uris: Set[str] = set()
        self._max_size = max_size

    def mark_read(self, uri: str):
        """Record that a URI was read."""
        if len(self._read_uris) >= self._max_size:
            # Evict oldest (approximate — sets are unordered)
            self._read_uris.pop()
        self._read_uris.add(uri)

    def has_read(self, uri: str) -> bool:
        """Check if a URI was read in this session."""
        return uri in self._read_uris

    def clear(self):
        self._read_uris.clear()


# =========================================================================
# Disclosure validation
# =========================================================================

# Patterns that indicate multiple trigger conditions (violates single-trigger principle)
# CJK keywords don't need word boundaries; English ones do
_MULTI_TRIGGER_CJK = re.compile(r"(或者|或是|或|以及|并且)")
_MULTI_TRIGGER_EN = re.compile(r"\b(and|or|as well as)\b", re.IGNORECASE)


def validate_disclosure(disclosure: Optional[str]) -> Optional[str]:
    """Validate a disclosure trigger string.

    Returns:
        None if valid, error message string if invalid.
    """
    if not disclosure or not disclosure.strip():
        return (
            "⚠️ Disclosure is required. A disclosure tells the AI when to "
            "surface this memory. Example: 'When the user asks about cooking'"
        )

    if _MULTI_TRIGGER_CJK.search(disclosure) or _MULTI_TRIGGER_EN.search(disclosure):
        return (
            "⚠️ Disclosure violates the single-trigger principle. "
            "Each memory should have exactly ONE trigger condition. "
            f"Found multi-trigger keyword in: \"{disclosure}\". "
            "Split into separate memories with distinct triggers."
        )

    return None  # Valid


# =========================================================================
# Priority guard
# =========================================================================

async def check_priority_zero_count(db_client, max_p0: int = 5) -> Optional[str]:
    """Warn if too many priority=0 (highest) memories exist.

    Returns:
        Warning message if count exceeds threshold, None otherwise.
    """
    try:
        from sqlalchemy import text
        async with db_client.session() as session:
            result = await session.execute(
                text("""
                    SELECT COUNT(DISTINCT e.child_uuid)
                    FROM edges e
                    JOIN paths p ON p.edge_id = e.id
                    WHERE e.priority = 0
                """)
            )
            count = result.scalar() or 0
            if count >= max_p0:
                return (
                    f"⚠️ You already have {count} priority-0 memories "
                    f"(max recommended: {max_p0}). Consider using priority 1-3 "
                    "for most memories. Priority 0 should be reserved for "
                    "core identity information."
                )
    except Exception:
        pass
    return None


# =========================================================================
# Global read tracker singleton
# =========================================================================

_tracker: Optional[ReadTracker] = None


def get_read_tracker() -> ReadTracker:
    global _tracker
    if _tracker is None:
        _tracker = ReadTracker()
    return _tracker
