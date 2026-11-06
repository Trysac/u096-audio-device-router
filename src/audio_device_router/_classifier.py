"""Name-based classification of virtual and loopback audio devices."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from itertools import islice

from ._devices import Kind
from ._errors import invalid_route

MAX_PATTERNS = 20
MAX_PATTERN_LENGTH = 100
MAX_NAME_LENGTH = 512
_KINDS = ("input", "output")

# Source: VB-Audio product names (CABLE Input, CABLE Output, VB-Audio, VoiceMeeter) and common
# Windows endpoint names (Stereo Mix, What U Hear, Wave Out Mix, loopback suffixes), compiled
# 2026-11-05. A bare "cable" is deliberately not a pattern, so "Cable Matters" stays physical.
DEFAULT_VIRTUAL_PATTERNS: tuple[str, ...] = (
    "CABLE Input",
    "CABLE Output",
    "VB-Audio",
    "VoiceMeeter",
    "Virtual",
)
DEFAULT_LOOPBACK_PATTERNS: tuple[str, ...] = (
    "Stereo Mix",
    "What U Hear",
    "Wave Out Mix",
    "(loopback)",
    "[Loopback]",
)


def fold(text: str) -> str:
    """Casefold ``text`` for case-insensitive comparison."""
    return text.casefold()


def validate_patterns(patterns: Iterable[str], label: str) -> tuple[str, ...]:
    """Validate a pattern list: at most 20 non-blank patterns of at most 100 characters.

    Raises:
        RouterError: ``invalid_route`` when the list violates a limit.
    """
    if isinstance(patterns, str):
        raise invalid_route(f"{label} must not be a plain string")
    try:
        items = tuple(islice(patterns, MAX_PATTERNS + 1))
    except TypeError:
        raise invalid_route(f"{label} must be an iterable of strings") from None
    if len(items) > MAX_PATTERNS:
        raise invalid_route(f"{label} has more than {MAX_PATTERNS} patterns")
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise invalid_route(f"{label} patterns must be non-empty strings")
        if len(item) > MAX_PATTERN_LENGTH:
            raise invalid_route(f"{label} pattern exceeds {MAX_PATTERN_LENGTH} characters")
    return items


def matches_token(folded_text: str, pattern: str) -> bool:
    """Return True when ``pattern`` occurs in ``folded_text`` at token boundaries.

    ``folded_text`` must already be casefolded. A match counts only when the characters before
    and after it are not letters or digits. A rejected occurrence does not end the search: later
    occurrences are tried too.
    """
    needle = fold(pattern)
    start = folded_text.find(needle)
    while start != -1:
        end = start + len(needle)
        before_ok = start == 0 or not folded_text[start - 1].isalnum()
        after_ok = end == len(folded_text) or not folded_text[end].isalnum()
        if before_ok and after_ok:
            return True
        start = folded_text.find(needle, start + 1)
    return False


@dataclass(frozen=True)
class ClassifierPatterns:
    """Name patterns used by :func:`classify`; at most 20 patterns of at most 100 characters.

    Attributes:
        virtual: Patterns marking virtual devices.
        loopback: Patterns marking loopback capture endpoints.
    """

    virtual: tuple[str, ...] = DEFAULT_VIRTUAL_PATTERNS
    loopback: tuple[str, ...] = DEFAULT_LOOPBACK_PATTERNS

    def __post_init__(self) -> None:
        object.__setattr__(self, "virtual", validate_patterns(self.virtual, "virtual"))
        object.__setattr__(self, "loopback", validate_patterns(self.loopback, "loopback"))


@dataclass(frozen=True)
class DeviceTraits:
    """Traits derived from a device name.

    Attributes:
        is_virtual: The name matches a virtual-device pattern.
        is_loopback: The name matches a loopback pattern.
    """

    is_virtual: bool
    is_loopback: bool


_DEFAULT_PATTERNS = ClassifierPatterns()


def classify(
    name: str,
    kind: Kind,
    *,
    patterns: ClassifierPatterns | None = None,
) -> DeviceTraits:
    """Classify a device name as virtual and/or loopback.

    Matching uses casefolded substrings at token boundaries, never regular expressions.

    Raises:
        RouterError: ``invalid_route`` for an unknown ``kind`` or a name that is not a string
            of at most 512 characters.
    """
    if kind not in _KINDS:
        raise invalid_route("kind must be 'input' or 'output'")
    if not isinstance(name, str):
        raise invalid_route("device name must be a string")
    if len(name) > MAX_NAME_LENGTH:
        raise invalid_route(f"device name longer than {MAX_NAME_LENGTH} characters")
    active = patterns if patterns is not None else _DEFAULT_PATTERNS
    folded = fold(name)
    return DeviceTraits(
        is_virtual=any(matches_token(folded, p) for p in active.virtual),
        is_loopback=any(matches_token(folded, p) for p in active.loopback),
    )
