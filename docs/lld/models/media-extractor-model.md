# `ExtractionResult` + `MediaExtractorProtocol` — Low-Level Design

## Responsibility
Data shape and extraction contract for the ffmpeg media extraction step.

## Implements
[Models diagram](../../uml/class/models.md)

## Fields — ExtractionResult
| Field | Type | Notes |
|---|---|---|
| `wav_path` | `str` | Absolute path to extracted 16 kHz mono WAV |
| `mp4_path` | `str` | Absolute path to normalised MP4 |

## Methods — MediaExtractorProtocol
| Method | Purpose | Edge cases |
|---|---|---|
| `extract(source_path, out_dir)` | Extract WAV + MP4 from source video | Raises `RuntimeError` on ffmpeg failure |

## Diagrams
| Diagram | Link |
|---|---|
| Class diagram | [models.md](../../uml/class/models.md) |

## Related
- Architecture: [ARCHITECTURE.md](../../../ARCHITECTURE.md)
- Source: `app/models/media_extractor.py`
