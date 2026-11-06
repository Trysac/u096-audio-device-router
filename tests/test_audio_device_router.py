"""Behavior tests for the public API of audio_device_router."""

from __future__ import annotations

import pytest

import audio_device_router


def test_normalize_trims_and_lowercases() -> None:
    assert audio_device_router.normalize("  Hello World ") == "hello world"


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_normalize_rejects_blank_input(value: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        audio_device_router.normalize(value)


def test_version_is_semver() -> None:
    parts = audio_device_router.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
