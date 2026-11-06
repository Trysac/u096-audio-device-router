"""Audio device model, backend protocol, in-memory backend and change detection."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import islice
from typing import Literal, Protocol, runtime_checkable

from ._errors import RouterError, invalid_route

logger = logging.getLogger(__name__)

Kind = Literal["input", "output"]

MAX_DEVICES = 256


@dataclass(frozen=True)
class AudioDevice:
    """One audio endpoint as reported by a backend.

    Attributes:
        id: Stable unique identifier of the endpoint.
        name: Human readable endpoint name.
        kind: ``"input"`` (capture) or ``"output"`` (playback).
        host_api: Name of the host API that exposes the endpoint, for example ``"WASAPI"``.
        channels: Maximum number of channels.
        sample_rates: Supported sample rates in Hz.
        is_default: Whether the OS marks this endpoint as the default one.
        is_loopback: Whether the backend knows the endpoint captures a render stream.
        is_virtual: Whether the backend knows the endpoint is a virtual device.
    """

    id: str
    name: str
    kind: Kind
    host_api: str
    channels: int
    sample_rates: tuple[int, ...]
    is_default: bool = False
    is_loopback: bool = False
    is_virtual: bool = False


@runtime_checkable
class DeviceBackend(Protocol):
    """Source of audio devices. A native backend (for example WASAPI) implements this."""

    def list_devices(self) -> list[AudioDevice]:
        """Return the endpoints that are currently present."""


@dataclass(frozen=True)
class DeviceChanges:
    """Difference between two enumerations, each tuple sorted by device id.

    Attributes:
        added: Devices present only in the second enumeration.
        removed: Devices present only in the first enumeration.
        changed: The second-enumeration version of devices whose id stayed but whose other
            fields changed.
    """

    added: tuple[AudioDevice, ...]
    removed: tuple[AudioDevice, ...]
    changed: tuple[AudioDevice, ...]


def check_devices(devices: Sequence[AudioDevice]) -> None:
    """Validate an enumeration: at most 256 devices and unique ids.

    Raises:
        RouterError: ``invalid_route`` when too many devices, ``duplicate_device_id`` when an
            id repeats.
    """
    if len(devices) > MAX_DEVICES:
        raise invalid_route(f"too many devices (max {MAX_DEVICES})")
    seen: set[str] = set()
    for device in devices:
        if device.id in seen:
            raise RouterError("duplicate_device_id", f"duplicate device id: {device.id[:80]}")
        seen.add(device.id)


def _snapshot(devices: Iterable[AudioDevice]) -> list[AudioDevice]:
    items = list(islice(devices, MAX_DEVICES + 1))
    check_devices(items)
    return items


class FakeBackend:
    """In-memory :class:`DeviceBackend` for tests and demos, holding at most 256 devices."""

    def __init__(self, devices: Iterable[AudioDevice] = ()) -> None:
        """Create a backend holding ``devices``.

        Raises:
            RouterError: on duplicate ids or more than 256 devices.
        """
        self._devices: dict[str, AudioDevice] = {d.id: d for d in _snapshot(devices)}

    def list_devices(self) -> list[AudioDevice]:
        """Return a copy of the present devices in plug order."""
        return list(self._devices.values())

    def plug(self, device: AudioDevice) -> None:
        """Add a device; a device with an existing id replaces the old one in place.

        Raises:
            RouterError: ``invalid_route`` when a new id would exceed 256 devices.
        """
        if device.id not in self._devices and len(self._devices) >= MAX_DEVICES:
            raise invalid_route(f"too many devices (max {MAX_DEVICES})")
        self._devices[device.id] = device
        logger.debug("device plugged, %d present", len(self._devices))

    def unplug(self, device_id: str) -> None:
        """Remove a device by id; unknown ids are ignored."""
        self._devices.pop(device_id, None)
        logger.debug("device unplugged, %d present", len(self._devices))


def diff_devices(before: Sequence[AudioDevice], after: Sequence[AudioDevice]) -> DeviceChanges:
    """Report which devices were added, removed or changed between two enumerations.

    Raises:
        RouterError: when either enumeration has duplicate ids or more than 256 devices.
    """
    check_devices(before)
    check_devices(after)
    old = {d.id: d for d in before}
    new = {d.id: d for d in after}
    added = tuple(new[i] for i in sorted(new.keys() - old.keys()))
    removed = tuple(old[i] for i in sorted(old.keys() - new.keys()))
    changed = tuple(new[i] for i in sorted(new.keys() & old.keys()) if new[i] != old[i])
    return DeviceChanges(added=added, removed=removed, changed=changed)
