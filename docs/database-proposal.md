# Database design

[`schema-proposal.dbml`](schema-proposal.dbml) is the readable ERD.
[`supabase/migrations/20261031000100_initial_readright_schema.sql`](../supabase/migrations/20261031000100_initial_readright_schema.sql)
creates the initial schema, including sessions, media lineage, service jobs,
normalized reading evidence, comprehension, and the dashboard summary view.
API code is grouped by feature, with shared CRUD mechanics under
`app/features/shared`.

## Decisions in this revision

- A session has `assigned_at` and optional `reading_started_at`; assignment is
  not counted as a reading start.
- A recording can reference its source recording. Video and extracted audio
  remain separate objects so vision and ASR can receive the appropriate media.
- A selected analysis stores WPM, word recognition, and reading level for
  dashboard queries. The dashboard view averages completed selected analyses.
- `service_jobs` tracks independent ASR, vision, prosody, and pronunciation
  attempts. The application owns dispatch, validation, normalized results, and
  user-facing status; the model services remain replaceable.
- Published passage content, tokens, questions, and choices are immutable; the
  database validates choices at publication and freezes submitted answers.
- Application tables use RLS without browser-facing table policies. The
  backend verifies the user token, then uses its server-only service key and
  scopes dashboard reads by that verified user ID.

The bad trailing `Ref` in the supplied sample was omitted. The job already has
an `analysis_id` foreign key; a job ID must not reference its own analysis ID.

## Apply locally or remotely

Install the [Supabase CLI](https://supabase.com/docs/guides/local-development/cli/getting-started),
then run `supabase start` and `supabase db reset` to apply migrations to a local
stack. Remote deployment is separate: link the intended project, review
`supabase db push --dry-run`, then run `supabase db push` when ready.

The current Supabase link targets the fresh project. On 2026-10-31, the linked
migration history confirmed `20261031000100` applied there. Before production,
confirm media and transcript retention, user deletion/storage cleanup,
supported grade values, service retry policy, and whether staff reporting
needs additional access policies.
