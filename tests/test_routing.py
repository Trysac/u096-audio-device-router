"""Tests for Route validation and resolve_routes."""

from __future__ import annotations

from itertools import permutations
from typing import Any

import pytest

from audio_device_router import AudioDevice, FakeBackend, Route, RouterError, resolve_routes


def make(device_id: str, name: str = "Mic", **kwargs: Any) -> AudioDevice:
    fields: dict[str, Any] = {
        "kind": "input",
        "host_api": "WASAPI",
        "channels": 2,
        "sample_rates": (44100, 48000),
    }
    fields.update(kwargs)
    return AudioDevice(id=device_id, name=name, **fields)


def test_name_match_beats_default_device() -> None:
    route = Route(role="mic", kind="input", name_contains=("usb",))
    devices = [
        make("b", "Mic (Realtek)", is_default=True),
        make("a", "Mic (USB)"),
    ]
    assert resolve_routes([route], devices).as_ids() == {"mic": "a"}


def test_default_device_wins_without_patterns() -> None:
    route = Route(role="mic", kind="input")
    devices = [make("a"), make("b", is_default=True)]
    assert resolve_routes([route], devices).as_ids() == {"mic": "b"}


def test_zero_score_tie_resolves_to_smaller_id() -> None:
    route = Route(role="mic", kind="input")
    devices = [make("z", "Mic 1"), make("m", "Mic 2")]
    assert resolve_routes([route], devices).as_ids() == {"mic": "m"}
    assert resolve_routes([route], devices[::-1]).as_ids() == {"mic": "m"}


def test_each_matching_pattern_adds_score() -> None:
    route = Route(role="mic", kind="input", name_contains=("usb", "realtek"))
    devices = [make("a", "Mic (USB)"), make("z", "Mic (USB Realtek)")]
    assert resolve_routes([route], devices).as_ids() == {"mic": "z"}


def test_pattern_needs_token_boundaries() -> None:
    route = Route(role="mic", kind="input", name_contains=("usb",))
    devices = [make("a", "Mic (USB2)"), make("b", "Mic", is_default=True)]
    assert resolve_routes([route], devices).as_ids() == {"mic": "b"}
    devices = [make("a", "Mic-USB"), make("b", "Mic", is_default=True)]
    assert resolve_routes([route], devices).as_ids() == {"mic": "a"}


def test_unicode_names_match_casefolded() -> None:
    route = Route(role="mic", kind="input", name_contains=("микрофон",))
    devices = [make("a", "Mic", is_default=True), make("b", "Микрофон (Realtek)")]
    assert resolve_routes([route], devices).as_ids() == {"mic": "b"}


def test_host_api_preference_outweighs_default() -> None:
    route = Route(role="mic", kind="input", prefer_host_api="wasapi")
    devices = [make("a", host_api="MME", is_default=True), make("b", host_api="WASAPI")]
    assert resolve_routes([route], devices).as_ids() == {"mic": "b"}


def test_previous_choice_is_sticky_until_unplugged() -> None:
    backend = FakeBackend([make("b", "Mic (Realtek)", is_default=True), make("a", "Mic (USB)")])
    route = Route(role="mic", kind="input", name_contains=("usb",))
    plan = resolve_routes([route], backend.list_devices(), previous={"mic": "b"})
    assert plan.as_ids() == {"mic": "b"}
    backend.unplug("b")
    plan = resolve_routes([route], backend.list_devices(), previous={"mic": "b"})
    assert plan.as_ids() == {"mic": "a"}


def test_previous_choice_must_pass_hard_filters() -> None:
    route = Route(role="mic", kind="input", min_channels=2)
    devices = [make("a"), make("b", channels=1), make("c", kind="output")]
    assert resolve_routes([route], devices, previous={"mic": "b"}).as_ids() == {"mic": "a"}
    assert resolve_routes([route], devices, previous={"mic": "c"}).as_ids() == {"mic": "a"}
    assert resolve_routes([route], devices, previous={"other": "b"}).as_ids() == {"mic": "a"}


def test_missing_required_role_and_strict_mode() -> None:
    route = Route(role="mic", kind="input")
    plan = resolve_routes([route], [make("o", kind="output")])
    assert plan.missing == ("mic",)
    assert plan.assignments == {}
    with pytest.raises(RouterError) as info:
        resolve_routes([route], [], strict=True)
    assert info.value.code == "no_matching_device"
    assert "mic" in str(info.value)


def test_strict_passes_when_everything_resolves() -> None:
    route = Route(role="mic", kind="input")
    assert resolve_routes([route], [make("a")], strict=True).as_ids() == {"mic": "a"}


def test_optional_roles_and_empty_enumeration() -> None:
    optional = Route(role="mon", kind="output", required=False)
    plan = resolve_routes([optional], [], strict=True)
    assert plan.missing == ()
    assert plan.as_ids() == {}
    assert resolve_routes([], [make("a")]).as_ids() == {}


def test_exclusive_conflict_picks_next_best() -> None:
    routes = [Route(role="cap", kind="input"), Route(role="mon", kind="input")]
    plan = resolve_routes(routes, [make("x", is_default=True), make("y")])
    assert plan.as_ids() == {"cap": "x", "mon": "y"}
    assert plan.conflicts == ("mon",)
    assert plan.missing == ()


def test_exclusive_conflict_without_alternative_is_missing() -> None:
    routes = [Route(role="cap", kind="input"), Route(role="mon", kind="input")]
    plan = resolve_routes(routes, [make("x")])
    assert plan.as_ids() == {"cap": "x"}
    assert plan.conflicts == ("mon",)
    assert plan.missing == ("mon",)


def test_optional_conflicting_role_is_not_missing() -> None:
    routes = [Route(role="cap", kind="input"), Route(role="mon", kind="input", required=False)]
    plan = resolve_routes(routes, [make("x")])
    assert plan.conflicts == ("mon",)
    assert plan.missing == ()


def test_sticky_device_already_taken_is_skipped() -> None:
    routes = [Route(role="r1", kind="input"), Route(role="r2", kind="input")]
    plan = resolve_routes(routes, [make("x"), make("y")], previous={"r1": "x", "r2": "x"})
    assert plan.as_ids() == {"r1": "x", "r2": "y"}
    assert plan.conflicts == ("r2",)


def test_conflicts_follow_route_order() -> None:
    routes = [Route(role=role, kind="input") for role in ("a", "b", "c")]
    plan = resolve_routes(routes, [make("x"), make("y")])
    assert plan.as_ids() == {"a": "x", "b": "y"}
    assert plan.conflicts == ("b", "c")
    assert plan.missing == ("c",)


def test_non_exclusive_routes_share_devices() -> None:
    routes = [
        Route(role="a", kind="input", exclusive=False),
        Route(role="b", kind="input", exclusive=False),
        Route(role="c", kind="input"),
    ]
    plan = resolve_routes(routes, [make("x")])
    assert plan.as_ids() == {"a": "x", "b": "x", "c": "x"}
    assert plan.conflicts == ()


def test_hard_filters_exclude_candidates() -> None:
    devices = [
        make("mono", "Mic mono", channels=1),
        make("out", "Speakers", kind="output"),
        make("hi", "Mic hi", sample_rates=(96000,)),
        make("ok", "Mic ok"),
    ]
    route = Route(role="mic", kind="input", min_channels=2, sample_rate=48000)
    assert resolve_routes([route], devices).as_ids() == {"mic": "ok"}
    output_route = Route(role="spk", kind="output")
    assert resolve_routes([output_route], devices).as_ids() == {"spk": "out"}


def test_require_loopback_uses_name_and_flag() -> None:
    devices = [
        make("lb", "Stereo Mix (Realtek)"),
        make("flag", "Odd Name", is_loopback=True),
        make("mic", "Mic", is_default=True),
    ]
    route = Route(role="cap", kind="input", require_loopback=True)
    assert resolve_routes([route], devices).as_ids() == {"cap": "flag"}
    assert resolve_routes([route], devices[:1] + devices[2:]).as_ids() == {"cap": "lb"}
    assert resolve_routes([route], devices[2:]).missing == ("cap",)


def test_require_virtual_uses_name_and_flag() -> None:
    devices = [
        make("v", "CABLE Output (VB-Audio Virtual Cable)"),
        make("f", "Odd Name", is_virtual=True),
        make("p", "Mic", is_default=True),
    ]
    route = Route(role="cable", kind="input", require_virtual=True)
    assert resolve_routes([route], devices).as_ids() == {"cable": "f"}
    assert resolve_routes([route], [devices[0], devices[2]]).as_ids() == {"cable": "v"}


def test_resolution_is_independent_of_device_order() -> None:
    devices = [
        make("a", "Mic (USB)"),
        make("b", "Mic (Realtek)", is_default=True),
        make("c", "Mic (USB)"),
        make("d", "Line"),
    ]
    routes = [
        Route(role="mic", kind="input", name_contains=("usb",)),
        Route(role="aux", kind="input"),
    ]
    results = {
        tuple(resolve_routes(routes, list(p)).as_ids().items()) for p in permutations(devices)
    }
    assert results == {(("mic", "a"), ("aux", "b"))}


def test_duplicate_device_ids_are_rejected() -> None:
    route = Route(role="mic", kind="input")
    with pytest.raises(RouterError) as info:
        resolve_routes([route], [make("a"), make("a")])
    assert info.value.code == "duplicate_device_id"


def test_device_and_route_bounds() -> None:
    route = Route(role="mic", kind="input")
    assert resolve_routes([route], [make(str(i)) for i in range(256)]).as_ids() == {"mic": "0"}
    with pytest.raises(RouterError) as info:
        resolve_routes([route], [make(str(i)) for i in range(257)])
    assert info.value.code == "invalid_route"
    routes = [Route(role=f"r{i}", kind="input", required=False) for i in range(32)]
    assert resolve_routes(routes, []).assignments == {}
    too_many = [Route(role=f"r{i}", kind="input") for i in range(33)]
    with pytest.raises(RouterError) as info2:
        resolve_routes(too_many, [])
    assert info2.value.code == "invalid_route"


def test_duplicate_roles_and_oversized_previous_are_rejected() -> None:
    route = Route(role="mic", kind="input")
    with pytest.raises(RouterError) as info:
        resolve_routes([route, route], [make("a")])
    assert info.value.code == "invalid_route"
    previous = {str(i): "a" for i in range(257)}
    with pytest.raises(RouterError) as info2:
        resolve_routes([route], [make("a")], previous=previous)
    assert info2.value.code == "invalid_route"


def test_device_with_unknown_kind_is_rejected() -> None:
    route = Route(role="mic", kind="input")
    with pytest.raises(RouterError) as info:
        resolve_routes([route], [make("a", kind="bogus")])
    assert info.value.code == "invalid_route"


def test_route_with_empty_pattern_is_invalid() -> None:
    with pytest.raises(RouterError) as info:
        Route(role="r", kind="input", name_contains=("",))
    assert info.value.code == "invalid_route"


def test_route_with_zero_min_channels_is_invalid() -> None:
    with pytest.raises(RouterError) as info:
        Route(role="r", kind="input", min_channels=0)
    assert info.value.code == "invalid_route"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"role": ""},
        {"role": "   "},
        {"role": "r" * 101},
        {"role": 5},
        {"kind": "duplex"},
        {"name_contains": "usb"},
        {"name_contains": 5},
        {"name_contains": (5,)},
        {"name_contains": tuple(f"p{i}" for i in range(21))},
        {"name_contains": ("x" * 101,)},
        {"min_channels": -1},
        {"min_channels": True},
        {"min_channels": 1.5},
        {"sample_rate": 0},
        {"sample_rate": 48000.0},
        {"sample_rate": True},
        {"prefer_host_api": ""},
        {"prefer_host_api": 5},
        {"prefer_host_api": "w" * 101},
        {"required": "yes"},
        {"exclusive": 1},
        {"require_loopback": None},
        {"require_virtual": 0},
    ],
)
def test_invalid_route_fields(kwargs: dict[str, Any]) -> None:
    fields: dict[str, Any] = {"role": "r", "kind": "input"}
    fields.update(kwargs)
    with pytest.raises(RouterError) as info:
        Route(**fields)
    assert info.value.code == "invalid_route"


def test_route_accepts_limits_and_coerces_lists() -> None:
    twenty = ["p" * 100 for _ in range(20)]
    route = Route(role="r" * 100, kind="output", name_contains=twenty)  # type: ignore[arg-type]
    assert route.name_contains == tuple(twenty)
    assert Route(role="r", kind="input").name_contains == ()
