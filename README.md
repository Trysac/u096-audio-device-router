# audio-device-router

[![PyPI version](https://img.shields.io/pypi/v/trysac-audio-device-router)](https://pypi.org/project/trysac-audio-device-router/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-audio-device-router)](LICENSE)
[![CI](https://github.com/Trysac/u096-audio-device-router/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u096-audio-device-router/actions/workflows/ci.yml)

Policy layer that classifies audio devices, resolves capture and playback roles to devices with sticky choices, and reports hot-plug changes

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-audio-device-router
# or
uv add trysac-audio-device-router
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import audio_device_router

# normalize() trims surrounding whitespace and lower-cases the text.
print(audio_device_router.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    audio_device_router.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
