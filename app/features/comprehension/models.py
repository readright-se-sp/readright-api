from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from app.features.shared.models import ResourceDefinition

COMPREHENSION_ATTEMPTS = ResourceDefinition(
    model_name="ComprehensionAttempt",
    slug="comprehension-attempts",
    table="comprehension_attempts",
    primary_key="attempt_id",
    field_types={
        "session_id": UUID,
        "attempt_number": int,
        "status": Literal["in_progress", "submitted", "abandoned"],
        "submitted_at": datetime | None,
        "score_earned": Decimal | None,
        "score_possible": Decimal | None,
    },
    create_fields=(
        "session_id",
        "attempt_number",
        "status",
        "submitted_at",
        "score_earned",
        "score_possible",
    ),
    required_create_fields=("session_id", "attempt_number"),
    update_fields=("status", "submitted_at", "score_earned", "score_possible"),
)

COMPREHENSION_ANSWERS = ResourceDefinition(
    model_name="ComprehensionAnswer",
    slug="comprehension-answers",
    table="comprehension_answers",
    primary_key="answer_id",
    field_types={
        "attempt_id": UUID,
        "question_id": UUID,
        "selected_choice_id": UUID | None,
        "answered_at": datetime | None,
    },
    create_fields=("attempt_id", "question_id", "selected_choice_id", "answered_at"),
    required_create_fields=("attempt_id", "question_id"),
    update_fields=("selected_choice_id", "answered_at"),
)

RESOURCES = (
    ("/attempts", COMPREHENSION_ATTEMPTS),
    ("/answers", COMPREHENSION_ANSWERS),
)

