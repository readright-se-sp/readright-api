# Runtime models

Python API models are kept together in [`app/models.py`](../app/models.py).
The file currently defines the learner dashboard response:

- `DashboardLearner`: authenticated learner and current grade.
- `DashboardSummary`: session counts and averages from completed selected runs.
- `DashboardSession`: recent session, passage, and optional selected reading.
- `LearnerDashboard`: response root.

The relational model and service-job records are defined by the SQL migration
and mirrored for review in [`schema-proposal.dbml`](schema-proposal.dbml). AI
inference implementations are not part of this backend.
