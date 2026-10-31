---
name: generate-and-verify
description: >
  Generate Python code for this project, then automatically verify it before handing
  back. Use this skill whenever the user asks you to implement, create, scaffold, or
  write any Python file, class, service, router, pipeline, or model. Trigger on:
  "implement X", "create a class for Y", "write the Z service", "scaffold this",
  "build the pipeline", "add a repository", or any request to produce new Python code.
  Do NOT hand back unverified code — always complete the full generate → verify → fix
  loop first.
---

# Generate-and-Verify Workflow

Every piece of code you write in this project goes through this loop before you
report it as done. Never skip a step, even if the code looks obviously correct.

## The Loop

```
GENERATE → SHOW → APPROVE → WRITE → PYRIGHT → SOLID-CHECK → if issues: FIX → repeat → DOCSTRINGS → UPDATE RELEVANT DOCS → REPORT → COMMIT?
```

### Step 1 — Generate

Draft the code following both project standards:
- **SOLID OOP** (see `.claude/skills/solid-oop/SKILL.md`): class-based controllers,
  service layer, Protocol interfaces, dependency injection via `Depends()`, one class
  one responsibility, no bare route functions.
- **Strong types** (see `.claude/skills/python-strong-types/SKILL.md`): Python 3.12
  syntax, all params and return types annotated, TypedDict/Pydantic/dataclass for
  data shapes, no bare `dict` or `list`.

Do **not** write any file yet.

### Step 2 — Show for Approval

Display the full code in a fenced block with the target file path as the label:

```python
# app/services/go2/scoring_engine.py
...
```

State the target path explicitly and wait for the user to approve before proceeding.
If the user requests changes, revise and show again. Do not write until approved.

### Step 3 — Write

Once approved, write the file to its correct project path.

### Step 4 — Pyright

Run pyright in strict mode on the file you just wrote:

```bash
cd /home/christian/dev/SE-Module-02
.venv/bin/pyright <file>
```

- **0 errors** → proceed to Step 3
- **Errors** → fix them in the file, re-run pyright, repeat until 0 errors

Do not proceed with pyright errors remaining.

### Step 5 — SOLID Self-Check

Read back what you just wrote and answer each question:

| Principle | Question | Pass? |
|---|---|---|
| **S** | Does each class have exactly one reason to change? | |
| **O** | Is new behaviour added via new classes, not edits to existing ones? | |
| **L** | Do all Protocol implementations return the same shape with the same semantics? | |
| **I** | Are Protocols narrow (≤4 methods)? No class forced to implement methods it doesn't use? | |
| **D** | Does each class depend on Protocols/abstractions, not concrete classes? Are concretes only wired in `dependencies.py`? | |

Any "no" → fix the violation, return to Step 2.

### Step 6 — Docstrings

Add a docstring to every class and public method in the file you just wrote.
Update the file in place (already approved, no second approval needed for docs-only additions).

**Style:** English, simplified tone, very concise — grammar can be sacrificed for brevity.
Keep technical jargon (ASR, WPM, Protocol, etc.). Write like you're leaving a quick note,
not formal documentation.

Good examples:
```python
class WhisperXTranscriber:
    """Holds pre-loaded WhisperX model refs and runs forced-alignment transcription."""

def load(self) -> None:
    """Loads the base model and alignment model into memory. Called once at startup."""

def transcribe(self, wav_path: str, passage_text: str) -> list[WordSegment]:
    """Runs ASR + forced alignment on a WAV file. Returns [] if no speech found."""

def get_transcriber_instance() -> WhisperXTranscriber:
    """Returns the singleton transcriber. Raises RuntimeError if not loaded yet."""

class TranscriberProtocol(Protocol):
    """Interface for ASR transcribers — pipeline depends on this, not the concrete class."""
```

Rules:
- One line for simple methods, 2-3 lines max for complex ones
- Don't restate the type annotations
- Don't use Args:/Returns: sections

### Step 7 — Relevant Docs

Update only the concise maintained docs listed in
`.claude/skills/design-docs/SKILL.md` when a code change affects their
contracts. Do not add sequence diagrams, a journal, or per-class design pages
unless the user asks.

### Step 8 — Report

Once the loop exits cleanly, report:

```
## Generated: <filename>

**Pyright:** 0 errors (strict)

**SOLID:**
- S ✓ <one line on what each class's single responsibility is>
- O ✓ <what Protocol/abstraction makes this open for extension>
- L ✓ / N/A
- I ✓ <protocol names and method counts>
- D ✓ <what is injected vs what is concrete, where concretes are wired>

**What was created:**
<bullet list of classes, protocols, and methods>
```

Show the final file content after the report.

### Step 9 — Commit

After the report, ask the user:

> Ready to commit? Say **go** to commit with conventional messages, or skip.

If the user says go (or any approval — "yes", "lgtm", "ship it"), invoke the
`git-conventional-commit` skill to stage, group, and commit the changes.
If they skip or say nothing, stop — never commit automatically.

## Shortcuts the Loop Allows

- If a file already has 0 pyright errors and clearly passes SOLID, one pass is enough
  — you don't need to iterate. The loop exists to catch mistakes, not to waste time.
- If a file has no logic (e.g. a pure TypedDict or Pydantic model file), skip the
  SOLID check — it doesn't apply to data-only files.
- Run pyright on multiple files at once if you generated several in one task:
  `.venv/bin/pyright app/services/go2/`
