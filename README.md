# audio-device-router

[![PyPI version](https://img.shields.io/pypi/v/trysac-audio-device-router)](https://pypi.org/project/trysac-audio-device-router/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-audio-device-router)](LICENSE)
[![CI](https://github.com/Trysac/u096-audio-device-router/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u096-audio-device-router/actions/workflows/ci.yml)

Policy layer that classifies audio devices, resolves capture and playback roles to devices with sticky choices, and reports hot-plug changes

## Problem

Real-time audio apps on Windows must pick the right devices for system loopback capture, the
microphone and a virtual cable, and the choice breaks when devices are renamed, plugged or
unplugged. Enumeration libraries such as sounddevice or PyAudio list devices but leave the
selection policy to every app. This library is a small policy layer behind a backend interface
that resolves roles deterministically and is tested without hardware.

Domain note: VB-Audio's `CABLE Input` is a playback endpoint that apps play into, and
`CABLE Output` is the recording endpoint apps capture from. WASAPI loopback captures from a
render (playback) endpoint.

## Install

```sh
pip install trysac-audio-device-router
# or
uv add trysac-audio-device-router
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
from audio_device_router import (
    AudioDevice,
    FakeBackend,
    Route,
    classify,
    diff_devices,
    resolve_routes,
)

print(classify("CABLE Input (VB-Audio Virtual Cable)", "output"))
# DeviceTraits(is_virtual=True, is_loopback=False)

backend = FakeBackend(
    [
        AudioDevice(
            id="b",
            name="Mic (Realtek)",
            kind="input",
            host_api="WASAPI",
            channels=2,
            sample_rates=(48000,),
            is_default=True,
        ),
        AudioDevice(
            id="a",
            name="Mic (USB)",
            kind="input",
            host_api="WASAPI",
            channels=1,
            sample_rates=(48000,),
        ),
    ]
)
before = backend.list_devices()

saved = {}  # role -> device id, persisted by the caller
routes = [Route(role="mic", kind="input", name_contains=("usb",))]
plan = resolve_routes(routes, before, previous=saved)
print(plan.as_ids())  # {'mic': 'a'}
saved = plan.as_ids()

# Hot-plug: the sticky choice is kept while it still passes the hard filters.
backend.unplug("a")
changes = diff_devices(before, backend.list_devices())
print([d.id for d in changes.removed])  # ['a']
plan = resolve_routes(routes, backend.list_devices(), previous=saved)
print(plan.missing)  # ('mic',) -> the USB mic no longer matches
```

## WASAPI extension point

The package ships no native backend. Implement the `DeviceBackend` protocol
(`list_devices() -> list[AudioDevice]`) on top of WASAPI or any audio library and pass its
result to `resolve_routes`; `FakeBackend` is the in-memory reference implementation.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
