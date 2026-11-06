"""Route definitions and the deterministic role resolver."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ._classifier import classify, fold, matches_token, validate_patterns
from ._devices import AudioDevice, Kind, check_devices
from ._errors import RouterError, invalid_route

logger = logging.getLogger(__name__)

MAX_ROUTES = 32
MAX_PREVIOUS = 256
MAX_TEXT_LENGTH = 100
NAME_MATCH_SCORE = 20
HOST_API_SCORE = 10
DEFAULT_SCORE = 5


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _valid_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= MAX_TEXT_LENGTH


@dataclass(frozen=True)
class Route:
    """A role that must be bound to one device.

    Attributes:
        role: Name of the role, 1 to 100 characters.
        kind: Direction of the wanted device.
        name_contains: Up to 20 patterns of up to 100 characters; each one found in the device
            name (casefolded, at token boundaries) adds 20 to the score.
        require_loopback: Only loopback devices qualify when True.
        require_virtual: Only virtual devices qualify when True.
        prefer_host_api: Host API that adds 10 to the score when it matches (casefolded).
        min_channels: Minimum channel count, at least 1.
        sample_rate: Sample rate the device must support, or None.
        required: Whether an unresolved role is reported in ``RoutingPlan.missing``.
        exclusive: Whether the role claims its device so later exclusive roles skip it.
    """

    role: str
    kind: Kind
    name_contains: tuple[str, ...] = ()
    require_loopback: bool = False
    require_virtual: bool = False
    prefer_host_api: str | None = None
    min_channels: int = 1
    sample_rate: int | None = None
    required: bool = True
    exclusive: bool = True

    def __post_init__(self) -> None:
        if not _valid_text(self.role):
            raise invalid_route("role must be 1 to 100 characters and not blank")
        if self.kind not in ("input", "output"):
            raise invalid_route("kind must be 'input' or 'output'")
        patterns = validate_patterns(self.name_contains, "name_contains")
        object.__setattr__(self, "name_contains", patterns)
        for flag in ("require_loopback", "require_virtual", "required", "exclusive"):
            if not isinstance(getattr(self, flag), bool):
                raise invalid_route(f"{flag} must be a boolean")
        if not _is_int(self.min_channels) or self.min_channels < 1:
            raise invalid_route("min_channels must be an integer >= 1")
        rate = self.sample_rate
        if rate is not None and (not _is_int(rate) or rate < 1):
            raise invalid_route("sample_rate must be a positive integer or None")
        api = self.prefer_host_api
        if api is not None and not _valid_text(api):
            raise invalid_route("prefer_host_api must be 1 to 100 characters or None")


@dataclass(frozen=True)
class RoutingPlan:
    """Result of :func:`resolve_routes`.

    Attributes:
        assignments: Role to device, in route order.
        missing: Required roles that got no device, in route order.
        conflicts: Roles whose preferred device was already taken by an earlier exclusive role.
    """

    assignments: dict[str, AudioDevice]
    missing: tuple[str, ...]
    conflicts: tuple[str, ...]

    def as_ids(self) -> dict[str, str]:
        """Return role to device id, ready to be persisted and passed back as ``previous``."""
        return {role: device.id for role, device in self.assignments.items()}


@dataclass(frozen=True)
class _Candidate:
    device: AudioDevice
    folded_name: str
    is_virtual: bool
    is_loopback: bool


def _prepare(devices: Sequence[AudioDevice]) -> list[_Candidate]:
    result: list[_Candidate] = []
    for device in devices:
        traits = classify(device.name, device.kind)
        result.append(
            _Candidate(
                device=device,
                folded_name=fold(device.name),
                is_virtual=traits.is_virtual or device.is_virtual,
                is_loopback=traits.is_loopback or device.is_loopback,
            )
        )
    return result


def _passes(route: Route, candidate: _Candidate) -> bool:
    device = candidate.device
    return (
        device.kind == route.kind
        and (candidate.is_loopback or not route.require_loopback)
        and (candidate.is_virtual or not route.require_virtual)
        and device.channels >= route.min_channels
        and (route.sample_rate is None or route.sample_rate in device.sample_rates)
    )


def _score(route: Route, candidate: _Candidate) -> int:
    score = 0
    for pattern in route.name_contains:
        if matches_token(candidate.folded_name, pattern):
            score += NAME_MATCH_SCORE
    if candidate.device.is_default:
        score += DEFAULT_SCORE
    api = route.prefer_host_api
    if api is not None and fold(candidate.device.host_api) == fold(api):
        score += HOST_API_SCORE
    return score


def _rank(route: Route, candidates: Sequence[_Candidate]) -> list[AudioDevice]:
    passing = [c for c in candidates if _passes(route, c)]
    passing.sort(key=lambda c: (-_score(route, c), c.device.id))
    return [c.device for c in passing]


def _preferred(
    role: str,
    ranked: Sequence[AudioDevice],
    previous: Mapping[str, str] | None,
) -> AudioDevice | None:
    sticky = previous.get(role) if previous is not None else None
    if sticky is not None:
        for device in ranked:
            if device.id == sticky:
                return device
    return ranked[0] if ranked else None


def _check_inputs(routes: Sequence[Route], previous: Mapping[str, str] | None) -> None:
    if len(routes) > MAX_ROUTES:
        raise invalid_route(f"too many routes (max {MAX_ROUTES})")
    roles: set[str] = set()
    for route in routes:
        if route.role in roles:
            raise invalid_route("duplicate role in routes")
        roles.add(route.role)
    if previous is not None and len(previous) > MAX_PREVIOUS:
        raise invalid_route(f"previous has more than {MAX_PREVIOUS} entries")


def resolve_routes(
    routes: Sequence[Route],
    devices: Sequence[AudioDevice],
    *,
    previous: Mapping[str, str] | None = None,
    strict: bool = False,
) -> RoutingPlan:
    """Resolve roles to devices deterministically.

    Routes are resolved in the given order. Hard filters (kind, loopback, virtual, channels,
    sample rate) remove candidates; the rest are ranked by an integer score (20 per matching
    name pattern, 10 for the preferred host API, 5 for the default device) with the smaller
    device id winning ties. A device listed for the role in ``previous`` keeps the role while it
    passes the hard filters. An exclusive route skips devices already claimed by an earlier
    exclusive route and is then listed in ``conflicts``.

    Raises:
        RouterError: ``invalid_route`` for more than 32 routes, 256 devices or 256 previous
            entries, or duplicate roles; ``duplicate_device_id`` for repeated device ids;
            ``no_matching_device`` when ``strict`` is True and a required role is unresolved.
    """
    _check_inputs(routes, previous)
    check_devices(devices)
    candidates = _prepare(devices)
    taken: set[str] = set()
    assignments: dict[str, AudioDevice] = {}
    missing: list[str] = []
    conflicts: list[str] = []
    for route in routes:
        ranked = _rank(route, candidates)
        chosen = _preferred(route.role, ranked, previous)
        if route.exclusive and chosen is not None and chosen.id in taken:
            conflicts.append(route.role)
            chosen = next((d for d in ranked if d.id not in taken), None)
        if chosen is None:
            if route.required:
                missing.append(route.role)
            continue
        assignments[route.role] = chosen
        if route.exclusive:
            taken.add(chosen.id)
    if strict and missing:
        message = f"no matching device for role(s): {', '.join(missing)}"
        raise RouterError("no_matching_device", message)
    logger.debug(
        "resolved %d routes: %d missing, %d conflicts",
        len(routes),
        len(missing),
        len(conflicts),
    )
    return RoutingPlan(assignments, tuple(missing), tuple(conflicts))
