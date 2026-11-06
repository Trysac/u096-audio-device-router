# Project record

## Objective

Policy layer that classifies audio devices, resolves capture and playback roles to devices with sticky choices, and reports hot-plug changes

## Scope

- In scope: the public API documented in [README.md](../README.md), typed and tested.
- Out of scope: anything that needs runtime dependencies or I/O without an accepted ADR.

## Timeline

| Date | Event |
|---|---|
| 2026 | Repository created from the factory utility template. |

## Effort metrics

Measured values only; a value that has not been measured stays "pending measurement".

| Metric | Value |
|---|---|
| Tokens (input / output) | 342758 / 64707 |
| Hours (human) | pending measurement |
| Cost (USD) | 0.5417 |

## Factory run u096 (measured from API usage)

| Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|
| generation | claude-sonnet-5-5 | yes | 2374 | 52878 | 0 | 4246 | 0.2672 |
| fix-1 | claude-sonnet-5-5 | no | 8 | 2453 | 8702 | 55905 | 0.0519 |
| audit | claude-sonnet-5-5 | no | 12 | 2981 | 27957 | 124223 | 0.1121 |
| fix-2 | claude-sonnet-5-5 | no | 6 | 1769 | 7739 | 40338 | 0.0411 |
| docs | claude-haiku-5-5 | no | 115646 | 4626 | 0 | 0 | 0.0694 |

Total: $0.5417. Prices: Anthropic list prices.
