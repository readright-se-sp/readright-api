# Runtime models

The dashboard feature keeps its API models in
[`app/features/dashboard/models.py`](../app/features/dashboard/models.py):

- `DashboardLearner`: authenticated learner and current grade.
- `DashboardSummary`: session counts and averages from completed selected runs.
- `DashboardSession`: recent session, passage, and optional selected reading.
- `LearnerDashboard`: response root.

The relational model is in the SQL migration and mirrored in
[`schema-proposal.dbml`](schema-proposal.dbml). AI inference implementations
are not part of this backend.

Shared Supabase access is provided through
[`app/dependencies/supabase.py`](../app/dependencies/supabase.py). Feature
packages depend on it; there is no general `services` layer.
