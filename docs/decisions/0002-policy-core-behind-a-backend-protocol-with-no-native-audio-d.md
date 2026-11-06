# Policy core behind a backend protocol, with no native audio dependency

Status: accepted (generated, pending human review)

## Context

Real-time audio applications on Windows must choose devices for loopback capture, the microphone and a virtual cable, and the choice breaks when devices are renamed, plugged or unplugged. Enumeration libraries list devices but leave selection policy to each application, and native audio code cannot be tested deterministically in CI.

## Decision

Ship only a pure policy core: immutable AudioDevice and Route values, a name classifier based on casefolded substrings at token boundaries (no user regular expressions), an integer scoring resolver with sticky previous choices and exclusive-device conflict reporting, and a sorted hot-plug diff. Devices come from a DeviceBackend protocol with an in-memory FakeBackend; a WASAPI backend is an extension point outside this package. All inputs are bounded (256 devices, 32 routes, 20 patterns of at most 100 characters) and every failure is a RouterError with a stable code.

## Consequences

The library has no runtime dependencies and is fully testable without hardware, with deterministic results independent of enumeration order. Applications must supply a real backend and persist the role-to-id mapping themselves. Name-based classification can misjudge unusual device names, which is mitigated by overridable ClassifierPatterns and by honouring the is_virtual and is_loopback flags a backend reports.
