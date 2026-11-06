"""Typed errors raised by audio_device_router."""

from __future__ import annotations

from typing import Literal

ErrorCode = Literal["invalid_route", "no_matching_device", "duplicate_device_id"]

_MAX_MESSAGE_LENGTH = 200


class RouterError(Exception):
    """Base error of the library.

    Attributes:
        code: Stable machine-readable error code. The message is capped at 200 characters and
            never contains more than a short excerpt of caller input.
    """

    def __init__(self, code: ErrorCode, message: str) -> None:
        if len(message) > _MAX_MESSAGE_LENGTH:
            message = message[: _MAX_MESSAGE_LENGTH - 3] + "..."
        super().__init__(message)
        self.code: ErrorCode = code


def invalid_route(message: str) -> RouterError:
    """Build an ``invalid_route`` error with the given message."""
    return RouterError("invalid_route", message)
