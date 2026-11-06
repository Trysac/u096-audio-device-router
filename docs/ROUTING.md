# Routing policy

`audio_device_router` is the policy layer that sits between an audio backend and an application.
It does not stream, mix or resample audio and never changes OS default devices. It answers one
question deterministically: which device should each role use right now?

## Scope

The package ships the policy core, a `DeviceBackend` protocol and an in-memory `FakeBackend`. There
is no native audio library and no Windows backend. A WASAPI backend is a documented extension
point: implement `list_devices() -> list[AudioDevice]` and pass its output to `resolve_routes`
and `diff_devices`. Enumeration libraries such as sounddevice or PyAudio list devices but leave
selection policy to every application; this library supplies that policy and is testable without
hardware.

## Domain note

VB-Audio's `CABLE Input` is a playback (render) endpoint that applications play into, and
`CABLE Output` is the recording (capture) endpoint that applications capture from. WASAPI loopback
captures from a render endpoint. `classify` therefore reports both CABLE endpoints as virtual and
reports names such as `Stereo Mix`, `What U Hear`, `Wave Out Mix`, `(loopback)` and `[Loopback]`
as loopback. A bare "cable" is not a pattern, so `Cable Matters` hardware stays physical.

## Matching

Patterns are casefolded substrings that must sit at token boundaries: the characters before and
after a match must not be letters or digits. User regular expressions are never used. A rejected
occurrence does not end the search; later occurrences are still tried. At most 20 patterns of at
most 100 characters are accepted, and device names are limited to 512 characters.

## Resolution

1. Hard filters remove candidates: kind, `require_loopback`, `require_virtual`, `min_channels` and
   `sample_rate`. A `require_*` flag set to `False` adds no constraint. A device counts as
   loopback or virtual when its name classifies that way or when its own flag says so.
2. Remaining candidates get an integer score: 20 for each matching `name_contains` pattern, 10 for
   a matching `prefer_host_api`, 5 for `is_default`. The smaller device id wins ties.
3. A device listed for the role in `previous` keeps the role while it passes the hard filters.
4. Routes are resolved in order. An exclusive route skips devices already claimed by an earlier
   exclusive route; the losing role is listed in `conflicts`. A required role without a device is
   listed in `missing`, and `strict=True` raises `RouterError` with code `no_matching_device`.

Bounds: at most 256 devices, 32 routes and 256 `previous` entries; violations raise `RouterError`
with code `invalid_route`. Repeated device ids raise `duplicate_device_id`.

## Demo

```python
from audio_device_router import AudioDevice, FakeBackend, Route, diff_devices, resolve_routes

usb = AudioDevice("usb", "Mic (USB)", "input", "WASAPI", 2, (48000,))
builtin = AudioDevice("in", "Mic (Realtek)", "input", "WASAPI", 2, (48000,), is_default=True)
backend = FakeBackend([builtin])
routes = [Route(role="mic", kind="input", name_contains=("usb",))]

before = backend.list_devices()
plan = resolve_routes(routes, before)
print(plan.as_ids())  # {'mic': 'in'}

backend.plug(usb)
after = backend.list_devices()
print([d.id for d in diff_devices(before, after).added])  # ['usb']
print(resolve_routes(routes, after, previous=plan.as_ids()).as_ids())  # {'mic': 'in'} (sticky)
print(resolve_routes(routes, after).as_ids())  # {'mic': 'usb'}
```

Persist `plan.as_ids()` yourself (the library has no profile files) and pass it back as
`previous` on the next run.
