# `ProperNounExtractorProtocol` — Low-Level Design

## Responsibility
Contract for deriving a passage's proper nouns so the classifier can exempt names from ASR-spelling penalties.

## Implements
N/A — protocol definition only.

## Constructor Dependencies
N/A

## Types
| Name | Kind | Purpose |
|---|---|---|
| `ProperNounExtractorProtocol` | `Protocol` | Interface the pipeline depends on; `extract(passage_text) -> list[str]`; concrete wired in `dependencies.py` |

## Diagrams
| Diagram | Link |
|---|---|
| Class diagram | [models.md](../../uml/class/models.md) |

## Related
- API contract: [api-contract.md](../../api-contract.md)
- Source: `app/models/proper_noun.py`
