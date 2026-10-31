# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

FastAPI application for **ReadRight Module 2** — the audio + video reading assessment pipeline. The current code extracts WAV + MP4, runs WhisperX ASR and MediaPipe CV inside the same deployment, runs GO2 and GO3 in parallel, merges the results into an `AssessmentResult`, and attempts to persist a flat session row to Supabase. The target architecture separates ASR and MediaPipe CV into private services; that is a proposal documented in [ARCHITECTURE.md](ARCHITECTURE.md), [AI service contracts](docs/ai-service-contracts.md), and [API payloads](docs/api-contract.md). Do not describe the target service split as implemented in runtime code until the application is changed.

## Commands

```bash
# Activate venv (always required)
source .venv/bin/activate

# Run dev server (from project root, not from app/)
uvicorn app.main:app --reload

# Type check (strict — must be 0 errors before committing)
.venv/bin/pyright app/

# Run tests
.venv/bin/pytest

# Install dependencies
pip install -r requirements.txt
# NOTE: ffmpeg system binary also required: sudo apt-get install ffmpeg
```

## Architecture

```
app/
  main.py                       # App factory + lifespan (WhisperX, MediaPipe, Supabase preload here)
  config.py                     # pydantic-settings Settings (API key, WhisperX, Supabase, CORS)
  dependencies.py               # FastAPI dependency providers — only place concretes are wired
  routers/
    analyze.py                  # AnalyzeController — POST /analyze, HTTP only
    health.py                   # HealthController — GET /health
  services/
    analysis_orchestrator.py    # AnalysisOrchestrator — async coordinator (GO2 ‖ GO3 → merge → DB)
    media_extractor.py          # MediaExtractor — ffmpeg subprocess, splits upload into wav + mp4
    go2/
      pipeline.py               # GO2Pipeline — passage fetch → ASR → miscue classify → score
      transcriber.py            # WhisperX ASR + forced alignment (singleton model)
      miscue_classifier.py      # Phil-IRI miscue taxonomy classifier
      miscue_reporter.py        # Per-miscue console breakdown (dev aid)
      proper_noun_extractor.py  # Capitalization-based proper-noun detector
      scoring_engine.py         # WPM, word-recognition %, reading level
    go3/
      pipeline.py               # GO3Pipeline — CV + prosody in sequence
      cv_detector.py            # MediaPipe finger-pointing / loss-of-place
      prosody_detector.py       # Amplitude-based monotone / inaudible detection
    db/
      supabase_client.py        # Lazy singleton supabase-py client (service key)
      passage_repository.py     # Fetches Phil-IRI passage text by passage_id
      session_repository.py     # Inserts session row after a successful run
  models/                       # Pydantic models, TypedDicts, and Protocols (one file per domain)
  utils/
    result_consolidator.py      # Merges GO2 + GO3 dicts into AssessmentResult
tests/                          # pytest — test_rr020..rr032 cover each ticket
```

### Key Patterns

- **Class-based controllers** — no bare route functions. Controllers register routes via `router.add_api_route()`.
- **Protocol interfaces** — concrete classes satisfy Protocols (`TranscriberProtocol`, `MiscueClassifierProtocol`, `CVDetectorProtocol`, etc.). Concretes are only constructed in `dependencies.py`.
- **Singleton at startup** — WhisperX + MediaPipe models and the Supabase client load once in the FastAPI `lifespan` context manager. Never load per request.
- **Async orchestration** — `AnalysisOrchestrator.run` writes the upload to a `tempfile.mkdtemp()`, runs `asyncio.gather(go2, go3)` via `asyncio.to_thread` (both pipelines are blocking), and cleans up the temp dir in `finally`.
- **Strong types** — Python 3.12, pyright strict. `type X = ...` aliases (PEP 695), `list[X]` not `List[X]`, `TypedDict` for data shapes. whisperx has no stubs — its calls use `# type: ignore[no-untyped-call]`, isolated to `transcriber.py`.

### Environment

`.env` (copy from `.env.example`):
```
API_KEY=your-secret-key
WHISPERX_MODEL=base.en           # size ladder: tiny.en < base.en < small.en < medium.en
WHISPERX_DEVICE=cpu
WHISPERX_COMPUTE_TYPE=int8       # lightest CPU footprint (~half the RAM, 2-4x faster); float16 on cuda
SUPABASE_URL=https://...supabase.co
SUPABASE_SERVICE_KEY=...         # service key, not anon — orchestrator persists sessions
ALLOWED_ORIGINS=["http://localhost:5173"]
```

`X-API-Key` header required on all `/analyze` calls.

## Task Status

| Issue | What | Status |
|---|---|---|
| RR-004 | Scaffold + stub `/analyze` | ✅ Done |
| RR-021 | WhisperX ASR + forced alignment | ✅ Done |
| RR-022 | Phil-IRI Miscue Classifier | ✅ Done |
| RR-023 | WPM + Scoring + Reading Level | ✅ Done |
| RR-020 | Real `/analyze` orchestrator | ✅ Done |
| RR-030 | GO3 CV detector (MediaPipe) | ✅ Done |
| RR-032 | GO3 prosody detector | ✅ Done |

These rows are historical implementation milestones, not current branch or roadmap status.

## Current runtime behavior

The current Python classifier returns `correct`, `mispronunciation`, `substitution`, `omission`, `insertion`, and `repetition`. The provisional database schema also includes `refusal_to_pronounce` and `unassessable`; those are not implemented by the current classifier or response model.

**Phil-IRI Miscue Rules** (current code):
- `correct` — edit distance ≤ 1 (also: dropped morphological inflections `-ed`, `-s`, `-es`, `-d`, `-ing`; proper nouns from the passage's whitelist)
- `mispronunciation` — phonetically similar, edit distance 2–3 (single-token only)
- `substitution` — completely different word OR an entire N↔M `replace` span (1 passage word → multi-token phrase counts as ONE substitution event)
- `omission` — passage word(s) absent from transcript; contiguous omitted run = ONE event with the joined phrase
- `insertion` — extra transcript word(s) not in passage; contiguous insertion = ONE event with the joined phrase
- `repetition` — same word OR phrase repeated consecutively in transcript; the repeated bigram/trigram is ONE event
- On ambiguous single-word classification: prefer conservative label (mispronunciation > substitution)
- ASR robustness: Filipino honorific stems (`mang`, `aling`, `ate`, `kuya`, `lola`, `lolo`) fused with a name in the transcript are split before alignment if both halves appear in the passage. A single transcript token with duration > 0.6s in a substitution emits a warning (likely ASR multi-word collapse).

**WPM + Scoring Formulas** (current code):
```python
wpm = total_passage_words / (last_word_end - first_word_start) * 60

# Error miscues = all 5 categories — each event counts as 1 error
# (mispronunciation + substitution + omission + insertion + repetition)
word_recognition_pct = (total_words - error_count) / total_words * 100

# Reading level — boundary ties qualify for the HIGHER classification
if word_recognition_pct >= 97:   reading_level = "Independent"
elif word_recognition_pct >= 91: reading_level = "Instructional"
else:                             reading_level = "Frustration"
```

**RR-020 orchestrator** (`app/services/analysis_orchestrator.py`):
- `tempfile.mkdtemp()` per request, `shutil.rmtree(..., ignore_errors=True)` in `finally`
- ffmpeg extraction → `asyncio.gather(go2, go3)` → `ResultConsolidator.merge`
- Empty `learner_id` skips the DB insert; the response still returns
- Session insert failure is **non-fatal** — flips `db_save_failed=True` on the response, learner still gets their result
- 500 + error code on pipeline failure:
  - `EXTRACTION_FAILED` — ffmpeg / media extractor threw
  - `ANALYSIS_FAILED` — either GO2 or GO3 pipeline threw
  - `CONSOLIDATION_FAILED` — `ResultConsolidator.merge` raised ValueError
- Errors return raw `{"error", "code"}` (not `{"detail": ...}`) via the custom exception handler in `main.py`

## Project Skills

`.claude/skills/` contains project-scoped workflow skills:
- `generate-and-verify` — the main coding loop: GENERATE → SHOW → APPROVE → WRITE → PYRIGHT → SOLID-CHECK → DOCSTRINGS → concise docs
- `solid-oop` — SOLID + class-based OOP patterns for this project
- `python-strong-types` — pyright strict, Python 3.12 typing rules
- `design-docs` — maintain only the concise architecture, API, model, and database docs

Always invoke `generate-and-verify` before writing any Python file.

## Docs

Keep documentation concise. The maintained set is `ARCHITECTURE.md`,
`docs/api-contract.md`, the database proposal and DBML, the AI boundary contract,
and model references under `docs/lld/models/` and `docs/uml/class/models.md`.
Proposals must be labeled as such; do not recreate sequence diagrams or a
change journal unless requested.
