from typing import Literal
from uuid import UUID

from app.features.shared.models import ResourceDefinition

GRADE_LEVELS = ResourceDefinition(
    model_name="GradeLevel",
    slug="grade-levels",
    table="grade_levels",
    primary_key="grade_id",
    field_types={"grade_id": int, "label": str, "sequence": int},
    create_fields=("grade_id", "label", "sequence"),
    required_create_fields=("grade_id", "label", "sequence"),
    update_fields=("label", "sequence"),
)

LEARNERS = ResourceDefinition(
    model_name="Learner",
    slug="learners",
    table="learners",
    primary_key="user_id",
    field_types={
        "user_id": UUID,
        "current_grade_id": int,
        "display_name": str | None,
    },
    create_fields=("user_id", "current_grade_id", "display_name"),
    required_create_fields=("user_id", "current_grade_id"),
    update_fields=("current_grade_id", "display_name"),
)

RESOURCES = (("/grade-levels", GRADE_LEVELS), ("/learners", LEARNERS))

