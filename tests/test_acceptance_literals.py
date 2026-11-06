"""Acceptance scenarios, quoted verbatim from the specification."""

from __future__ import annotations

from typing import Any

import pytest

from audio_device_router import AudioDevice, Route, RouterError, resolve_routes

SCENARIOS = (
    "For Route(role='mic', kind='input', name_contains=('usb',)) and devices AudioDevice(id='b', name='Mic (Realtek)', is_default=True, ...) and AudioDevice(id='a', name='Mic (USB)', ...), resolve_routes(...).as_ids() == {'mic': 'a'} (20 beats 5); two candidates scoring 0 resolve to the smaller id",  # noqa: E501
    "With previous={'mic': 'b'}, 'b' keeps the role while it passes the hard filters even though 'a' scores higher; once 'b' is unplugged, 'a' is chosen",  # noqa: E501
    "Two exclusive routes 'cap' then 'mon' whose best device is the same 'x' give assignments {'cap': 'x', 'mon': <next best>} and plan.conflicts == ('mon',); with no other candidate 'mon' is in missing too",  # noqa: E501
    "Route(role='r', kind='input', name_contains=('',)) and Route(role='r', kind='input', min_channels=0) raise RouterError with code == 'invalid_route'; two devices with id 'a' raise code == 'duplicate_device_id'; 257 devices or 33 routes raise code == 'invalid_route'",  # noqa: E501
)


def make(device_id: str, name: str = "Mic", **kwargs: Any) -> AudioDevice:
    fields: dict[str, Any] = {
        "kind": "input",
        "host_api": "WASAPI",
        "channels": 2,
        "sample_rates": (44100,),
    }
    fields.update(kwargs)
    return AudioDevice(id=device_id, name=name, **fields)


def test_scenarios_listed() -> None:
    assert len(SCENARIOS) == 4


def test_sticky_previous_then_unplugged() -> None:
    route = Route(role="mic", kind="input", name_contains=("usb",))
    b = make("b", "Mic (Realtek)", is_default=True)
    a = make("a", "Mic (USB)")
    plan = resolve_routes([route], [b, a], previous={"mic": "b"})
    assert plan.as_ids() == {"mic": "b"}
    plan = resolve_routes([route], [a], previous={"mic": "b"})
    assert plan.as_ids() == {"mic": "a"}


def test_exclusive_conflict() -> None:
    cap = Route(role="cap", kind="input")
    mon = Route(role="mon", kind="input")
    x = make("x", is_default=True)
    y = make("y")
    plan = resolve_routes([cap, mon], [x, y])
    assert plan.as_ids() == {"cap": "x", "mon": "y"}
    assert plan.conflicts == ("mon",)
    plan = resolve_routes([cap, mon], [x])
    assert plan.conflicts == ("mon",)
    assert "mon" in plan.missing


def test_invalid_routes_and_bounds() -> None:
    with pytest.raises(RouterError) as err:
        Route(role="r", kind="input", name_contains=("",))
    assert err.value.code == "invalid_route"
    with pytest.raises(RouterError) as err:
        Route(role="r", kind="input", min_channels=0)
    assert err.value.code == "invalid_route"
    with pytest.raises(RouterError) as err:
        resolve_routes([], [make("a"), make("a")])
    assert err.value.code == "duplicate_device_id"
    with pytest.raises(RouterError) as err:
        resolve_routes([], [make(str(i)) for i in range(257)])
    assert err.value.code == "invalid_route"
    with pytest.raises(RouterError) as err:
        resolve_routes([Route(role=f"r{i}", kind="input") for i in range(33)], [])
    assert err.value.code == "invalid_route"
