"""Policy layer that classifies audio devices, resolves roles to devices and reports changes."""

from __future__ import annotations

import logging

from ._classifier import ClassifierPatterns, DeviceTraits, classify
from ._devices import AudioDevice, DeviceBackend, DeviceChanges, FakeBackend, diff_devices
from ._errors import RouterError
from ._routing import Route, RoutingPlan, resolve_routes

logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    "AudioDevice",
    "ClassifierPatterns",
    "DeviceBackend",
    "DeviceChanges",
    "DeviceTraits",
    "FakeBackend",
    "Route",
    "RouterError",
    "RoutingPlan",
    "__version__",
    "classify",
    "diff_devices",
    "resolve_routes",
]

__version__ = "0.1.0"
