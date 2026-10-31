# Database proposal

The accompanying [`schema-proposal.dbml`](schema-proposal.dbml) captures a
candidate PostgreSQL model for learner sessions, recordings, rerunnable
analyses, independently dispatched AI jobs, normalized evidence, and
comprehension attempts.

**This is a discussion artifact, not the current database schema or a migration.**
The repository currently reads passages and writes a flat `sessions` row in
Supabase. Confirm ownership, privacy/retention rules, reporting queries, and
service boundaries before implementing this proposal. Table names, fields,
enums, indexes, and payloads may change.

## Main modeling choices

- `sessions` captures the learner, assigned passage, grade at assignment, and
  policy version. Later grade promotion does not rewrite historical sessions.
- `recordings` stores private object-storage coordinates and media metadata;
  binary media and expiring URLs do not belong in PostgreSQL.
- `reading_analyses` preserves reruns and records the selected result plus the
  pipeline and scoring policy versions.
- `service_jobs` records each ASR, vision, prosody, or pronunciation attempt.
  Raw JSON is diagnostic; normalized event/observation rows drive reporting.
- `reading_events` stores word/phrase-level reading evidence. A review is an
  overlay on the original machine classification, so machine output remains
  unchanged.
- `phoneme_events` is optional pronunciation evidence. A missing actual
  phoneme must not be fabricated.
- `comprehension_answers` stores learner selections. Correctness is resolved
  server-side; do not expose `question_choices.is_correct` in learner payloads.

## Database rules needing implementation review

DBML does not express every PostgreSQL invariant. Implement and review these
with migrations, constraints, triggers, or transaction logic as appropriate:

- one selected analysis per session;
- one current service job per analysis and service kind;
- immutable published passage content/questions/choices (retirement is
  allowed, mutation is not);
- positive token and question positions, ordered content, and valid question
  choice counts;
- exactly one correct choice for each published question;
- answers may select only a choice belonging to their question, and submitted
  attempts are frozen;
- cross-check that session, analysis, recording, passage token, event, and
  service-job references all belong to the same assessment context;
- required timestamp/status transitions and valid duration/confidence ranges.

The previous final `Ref` line in the supplied sample was malformed and
redundant: `service_jobs.analysis_id` already declares its foreign key to
`reading_analyses.analysis_id`. It is omitted from the DBML copy.

## Review points

- Decide whether `auth.users` stays in Supabase Auth and whether learner records
  are one-to-one with that identity.
- Decide whether a session may have more than one recording and whether media
  kind should distinguish video-with-audio from standalone audio.
- A video upload produces a video input for CV and an extracted audio input for
  ASR. The sample's `source_recording_id` note points to the ASR audio; confirm
  whether the derived WAV is a separate `recordings` row and whether to add a
  `derived_from_recording_id` or artifact table to preserve provenance.
- The CV result example has structured evidence intervals, while
  `behavior_observations` currently has only `evidence_note`. Add start/end
  columns if learner or staff views need to seek to evidence timestamps.
- Clarify `partial` analysis semantics, required versus optional services,
  retries, and the selected-analysis workflow.
- Confirm whether transcripts and evidence require row-level encryption,
  access auditing, and deletion propagation to object storage.
- Add explicit indexes and retention policy from expected workloads rather
  than treating this initial index list as final.
