# `MiscueCounts` / `MiscueClassifierProtocol` — Low-Level Design

## Responsibility
Defines the output shape for GO2 miscue classification and the protocol interface consumed by the pipeline.

## Implements
N/A — data shape and protocol definition only.

## Constructor Dependencies
N/A

## Types
| Name | Kind | Purpose |
|---|---|---|
| `MiscueType` | `Literal` type alias | The 6 current runtime labels: `correct`, `mispronunciation`, `substitution`, `omission`, `insertion`, `repetition` |
| `MiscueCounts` | `TypedDict` | Per-category count dict returned by `MiscueClassifier.classify()` |
| `MiscueDetail` | `TypedDict` | One aligned word decision: `miscue_type`, `passage_word`/`transcript_word` (either may be `None`), `start`/`end` timing (`None` when no spoken word) |
| `MiscueClassifierProtocol` | `Protocol` | Interface the pipeline depends on; `classify()` + `detail()`, both accept optional `proper_nouns: list[str]`; concrete wired in `dependencies.py` |
| `MiscueReporterProtocol` | `Protocol` | Interface for printing `MiscueDetail`s after analysis; concrete (`MiscueReporter`) wired in `dependencies.py` |

## Diagrams
| Diagram | Link |
|---|---|
| Models class diagram | [models.md](../../uml/class/models.md) |

## Related
- API contract: [api-contract.md](../../api-contract.md)
- Source: `app/models/miscue.py`

The provisional database enum includes `refusal_to_pronounce` and
`unassessable`; they are not current `MiscueType` values.
