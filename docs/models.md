# Runtime models

The relational schema is defined by the SQL migration and mirrored in
[`schema-proposal.dbml`](schema-proposal.dbml). CRUD request models are generated
from each feature's `models.py`, which lists writable fields and types:

- `learners`: grade levels and learner profiles.
- `content`: passages, passage tokens, comprehension questions and choices.
- `reading`: sessions, recordings, analyses, reading events, behavior
  observations and phoneme events.
- `service_jobs`: external-service attempts and result payloads.
- `mai`: MAI request/response validation, SQS submission, worker processing,
  polling, and transaction-backed response persistence.
- `comprehension`: attempts and answers.
- `dashboard`: learner-facing dashboard response models.

`auth.users` belongs to Supabase Auth. `learner_dashboard_summary` is a
read-only database view. Shared Supabase access is provided by
[`app/dependencies/supabase.py`](../app/dependencies/supabase.py); database
operations stay inside their feature's controller, service and repository.
