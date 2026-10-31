# `ProsodyFlags` + `ProsodyDetectorProtocol` — Low-Level Design

## Responsibility
Defines the data shape and interface contract for GO3 prosody detection — no logic.

## Implements
N/A — this file defines the Protocol, not an implementation.

## Constructor Dependencies
None — TypedDict and Protocol only.

## Methods
| Method | Purpose | Edge cases |
|---|---|---|
| `detect(wav_path: str) → ProsodyFlags` | Returns three prosody flags from a WAV file | Defined on Protocol only; impl handles short audio |

## Diagrams
| Diagram | Link |
|---|---|
| Class diagram | [models.md](../../uml/class/models.md) |

## Related
- AI service contract: [ai-service-contracts.md](../../ai-service-contracts.md)
- Source: `app/models/prosody_detector.py`
