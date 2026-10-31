---
name: dev-journal
description: >
  Write an implementation journal only when the user explicitly asks to log a
  change, track an iteration, or update a changelog. Do not recreate the journal
  automatically after code changes.
  One entry per iteration — never rewrite existing entries.
---

# Dev Journal Skill

The project no longer keeps an automatic `docs/JOURNAL.md`. Create or update a
journal only when the user explicitly asks for one. If requested, keep entries
concise and preserve existing history unless the user directs otherwise.

---

## Entry Format

```markdown
---

### YYYY-MM-DD · Iteration N — <short title>

**Added**
- `path/to/file.py` — one line on what it does

**Changed**
- `path/to/file.py` — what changed and why

**Removed**
- `path/to/file.py` — why it was removed

**Design Decisions**
- <decision> — <reason>

**Verification**
- Pyright: `0 errors`
- SOLID: ✓ / ⚠ `<note if any violation was found and fixed>`
- Docs: list only the concise maintained docs that changed
```

---

## Rules

- **One entry per generate-and-verify iteration** — not one per file
- **Concise** — bullet points only, no paragraphs
- **Added / Changed / Removed** — only include sections that apply; skip empty ones
- **Design Decisions** — only log non-obvious choices (e.g. why Protocol over ABC,
  why TypedDict over dataclass for a specific shape). Skip obvious ones.
- **Iteration N** — increment from the last entry in the file; start at 1 if the
  file is new
- **Short title** — name of the feature, class, or task (e.g. `GO2 Scaffold`,
  `MiscueClassifier`, `Stub /analyze endpoint`)

---

## File Location (only when requested)

`docs/JOURNAL.md` — in the project root `docs/` folder.

If the file does not exist yet, create it with this header first:

```markdown
# Dev Journal — ReadRight GO2

> Append-only log of each build iteration. Newest entries at the bottom.

---
```

Then append the first entry below the header.

---

## When to Run

Run only after an explicit user request. This is not part of the default
generate-and-verify workflow.

Do not show the journal entry for approval — it is a log, not code. Just write it.
