"""Tests for classification, devices, the fake backend and change detection."""

from __future__ import annotations

import dataclasses
import logging
from dataclasses import replace
from typing import Any

import pytest

from audio_device_router import (
    AudioDevice,
    ClassifierPatterns,
    DeviceBackend,
    DeviceChanges,
    DeviceTraits,
    FakeBackend,
    RouterError,
    classify,
    diff_devices,
)


def make(device_id: str, name: str = "Mic", **kwargs: Any) -> AudioDevice:
    fields: dict[str, Any] = {
        "kind": "input",
        "host_api": "WASAPI",
        "channels": 2,
        "sample_rates": (44100, 48000),
    }
    fields.update(kwargs)
    return AudioDevice(id=device_id, name=name, **fields)


def test_classify_virtual_cable_endpoints() -> None:
    expected = DeviceTraits(is_virtual=True, is_loopback=False)
    assert classify("CABLE Input (VB-Audio Virtual Cable)", "output") == expected
    assert classify("CABLE Output (VB-Audio Virtual Cable)", "input") == expected


def test_classify_loopback_endpoints() -> None:
    assert classify("Stereo Mix (Realtek)", "input").is_loopback is True
    assert classify("Speakers (Realtek) [Loopback]", "input").is_loopback is True
    assert classify("Speakers (Realtek) [Loopback]", "output").is_virtual is False


def test_classify_physical_devices() -> None:
    physical = DeviceTraits(is_virtual=False, is_loopback=False)
    assert classify("Microphone (USB)", "input") == physical
    assert classify("Microphone (Cable Matters USB)", "input") == physical


@pytest.mark.parametrize(
    ("name", "virtual", "loopback"),
    [
        ("VoiceMeeter Output (VB-Audio VoiceMeeter VAIO)", True, False),
        ("vb-audio point", True, False),
        ("Virtualbox Virtual Mic", True, False),
        ("Mic-Virtual", True, False),
        ("マイク (Virtual)", True, False),
        ("What U Hear (Sound Blaster)", False, True),
        ("Wave Out Mix", False, True),
        ("Speakers (loopback)", False, True),
        ("Stereo Mix, Virtual", True, True),
    ],
)
def test_classify_matches_at_token_boundaries(name: str, virtual: bool, loopback: bool) -> None:
    assert classify(name, "input") == DeviceTraits(is_virtual=virtual, is_loopback=loopback)


@pytest.mark.parametrize(
    "name",
    [
        "Virtualization Mixer",
        "CABLE Input2",
        "Stereo Mixer",
        "VoiceMeeterPro",
        "Mic Virtual2",
        "Microphone (Cable Matters USB)",
        "",
    ],
)
def test_classify_rejects_near_misses(name: str) -> None:
    assert classify(name, "input") == DeviceTraits(is_virtual=False, is_loopback=False)


def test_classify_custom_patterns_override_defaults() -> None:
    custom = ClassifierPatterns(virtual=("loop",), loopback=())
    assert classify("My Loop", "input", patterns=custom).is_virtual is True
    assert classify("CABLE Input", "output", patterns=custom).is_virtual is False
    assert classify("Stereo Mix", "input", patterns=custom).is_loopback is False
    assert ClassifierPatterns().virtual[0] == "CABLE Input"


def test_classify_rejects_bad_inputs() -> None:
    bad_kind: Any = "duplex"
    bad_name: Any = 42
    for args in (("Mic", bad_kind), (bad_name, "input"), ("a" * 513, "input")):
        with pytest.raises(RouterError) as info:
            classify(*args)
        assert info.value.code == "invalid_route"
    assert classify("a" * 512, "input").is_virtual is False


@pytest.mark.parametrize(
    "patterns",
    [
        tuple(f"p{i}" for i in range(21)),
        ("x" * 101,),
        ("",),
        ("   ",),
        (1,),
        "abc",
        5,
    ],
)
def test_classifier_patterns_enforce_limits(patterns: Any) -> None:
    with pytest.raises(RouterError) as info:
        ClassifierPatterns(virtual=patterns)
    assert info.value.code == "invalid_route"
    with pytest.raises(RouterError):
        ClassifierPatterns(loopback=patterns)


def test_classifier_patterns_accept_limits() -> None:
    twenty = tuple(f"p{i}" for i in range(20))
    assert len(ClassifierPatterns(virtual=twenty).virtual) == 20
    assert len(ClassifierPatterns(virtual=("x" * 100,)).virtual[0]) == 100
    assert ClassifierPatterns(virtual=["a"]).virtual == ("a",)


def test_router_error_has_code_and_truncates_message() -> None:
    err = RouterError("invalid_route", "x" * 500)
    assert err.code == "invalid_route"
    assert len(str(err)) == 200
    assert str(RouterError("no_matching_device", "short")) == "short"
    assert isinstance(err, Exception)


def test_audio_device_is_immutable() -> None:
    device = make("a")
    with pytest.raises(dataclasses.FrozenInstanceError):
        device.name = "other"  # type: ignore[misc]


def test_fake_backend_lists_in_plug_order_and_returns_copy() -> None:
    backend = FakeBackend([make("b"), make("a")])
    listed = backend.list_devices()
    assert [d.id for d in listed] == ["b", "a"]
    listed.clear()
    assert len(backend.list_devices()) == 2
    assert FakeBackend().list_devices() == []


def test_fake_backend_plug_and_unplug() -> None:
    backend = FakeBackend()
    backend.plug(make("a"))
    backend.plug(make("b"))
    backend.unplug("a")
    backend.unplug("missing")
    assert [d.id for d in backend.list_devices()] == ["b"]


def test_plug_with_existing_id_replaces_in_place() -> None:
    backend = FakeBackend([make("a", "Old"), make("b")])
    backend.plug(make("a", "New"))
    assert [(d.id, d.name) for d in backend.list_devices()] == [("a", "New"), ("b", "Mic")]


def test_fake_backend_rejects_duplicate_ids() -> None:
    with pytest.raises(RouterError) as info:
        FakeBackend([make("a"), make("a")])
    assert info.value.code == "duplicate_device_id"
    with pytest.raises(RouterError) as long_info:
        FakeBackend([make("a" * 300), make("a" * 300)])
    assert len(str(long_info.value)) <= 200


def test_fake_backend_capacity() -> None:
    full = [make(str(i)) for i in range(256)]
    backend = FakeBackend(full)
    backend.plug(make("5", "Renamed"))
    with pytest.raises(RouterError) as info:
        backend.plug(make("extra"))
    assert info.value.code == "invalid_route"
    with pytest.raises(RouterError) as info2:
        FakeBackend([make(str(i)) for i in range(257)])
    assert info2.value.code == "invalid_route"


def test_fake_backend_satisfies_protocol() -> None:
    assert isinstance(FakeBackend(), DeviceBackend)
    assert not isinstance(object(), DeviceBackend)


def test_diff_devices_sorted_and_name_change_only_in_changed() -> None:
    old_b = make("b", "Old")
    backend = FakeBackend([make("c"), make("a"), old_b])
    before = backend.list_devices()
    backend.unplug("c")
    backend.plug(make("z"))
    backend.plug(make("d"))
    new_b = replace(old_b, name="New")
    backend.plug(new_b)
    after = backend.list_devices()
    changes = diff_devices(before, after)
    assert tuple(d.id for d in changes.added) == ("d", "z")
    assert tuple(d.id for d in changes.removed) == ("c",)
    assert changes.changed == (new_b,)
    assert isinstance(changes.added, tuple)


def test_diff_devices_empty_and_identical() -> None:
    assert diff_devices([], []) == DeviceChanges((), (), ())
    same = [make("a")]
    assert diff_devices(same, list(same)) == DeviceChanges((), (), ())


def test_diff_devices_validates_input() -> None:
    with pytest.raises(RouterError) as info:
        diff_devices([make("a"), make("a")], [])
    assert info.value.code == "duplicate_device_id"
    with pytest.raises(RouterError) as info2:
        diff_devices([], [make(str(i)) for i in range(257)])
    assert info2.value.code == "invalid_route"


def test_package_logger_has_only_a_null_handler() -> None:
    handlers = logging.getLogger("audio_device_router").handlers
    assert any(isinstance(h, logging.NullHandler) for h in handlers)
