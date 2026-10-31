# `ScoringResult` / `ScoringEngineProtocol` — Low-Level Design

## Responsibility
Defines the output shape for GO2 scoring and the protocol interface consumed by the pipeline / FastAPI DI layer.

## Implements
N/A — data shape and protocol definition only.

## Constructor Dependencies
N/A

## Types
| Name | Kind | Purpose |
|---|---|---|
| `ScoringResult` | `TypedDict` | Three-field output of `ScoringEngine.score()`: `wpm: float`, `word_recognition_pct: float`, `reading_level: ReadingLevel` |
| `ScoringEngineProtocol` | `Protocol` | Single-method interface (`score(...) -> ScoringResult`); concrete wired in `dependencies.py` via `get_scoring_engine()` |

## Diagrams
| Diagram | Link |
|---|---|
| Models class diagram | [models.md](../../uml/class/models.md) |

## Related
- API contract: [api-contract.md](../../api-contract.md)
- Source: `app/models/scoring.py`
