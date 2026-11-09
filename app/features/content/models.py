from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from app.features.shared.models import ResourceDefinition

PASSAGES = ResourceDefinition(
    model_name="Passage",
    slug="passages",
    table="passages",
    primary_key="passage_id",
    field_types={
        "title": str,
        "difficulty_grade_id": int,
        "language_code": str,
        "content": str,
        "status": Literal["draft", "published", "retired"],
        "published_at": datetime | None,
    },
    create_fields=(
        "title",
        "difficulty_grade_id",
        "language_code",
        "content",
        "status",
        "published_at",
    ),
    required_create_fields=("title", "difficulty_grade_id", "language_code", "content"),
    update_fields=(
        "title",
        "difficulty_grade_id",
        "language_code",
        "content",
        "status",
        "published_at",
    ),
)

PASSAGE_TOKENS = ResourceDefinition(
    model_name="PassageToken",
    slug="passage-tokens",
    table="passage_tokens",
    primary_key="token_id",
    field_types={
        "passage_id": UUID,
        "position": int,
        "token_text": str,
        "is_proper_noun": bool,
    },
    create_fields=("passage_id", "position", "token_text", "is_proper_noun"),
    required_create_fields=("passage_id", "position", "token_text"),
    update_fields=("position", "token_text", "is_proper_noun"),
)

COMPREHENSION_QUESTIONS = ResourceDefinition(
    model_name="ComprehensionQuestion",
    slug="comprehension-questions",
    table="comprehension_questions",
    primary_key="question_id",
    field_types={
        "passage_id": UUID,
        "question_order": int,
        "prompt": str,
        "points_possible": Decimal,
    },
    create_fields=("passage_id", "question_order", "prompt", "points_possible"),
    required_create_fields=("passage_id", "question_order", "prompt"),
    update_fields=("question_order", "prompt", "points_possible"),
)

QUESTION_CHOICES = ResourceDefinition(
    model_name="QuestionChoice",
    slug="question-choices",
    table="question_choices",
    primary_key="choice_id",
    field_types={
        "question_id": UUID,
        "choice_order": int,
        "choice_text": str,
        "is_correct": bool,
    },
    create_fields=("question_id", "choice_order", "choice_text", "is_correct"),
    required_create_fields=("question_id", "choice_order", "choice_text"),
    update_fields=("choice_order", "choice_text", "is_correct"),
)

RESOURCES = (
    ("/passages", PASSAGES),
    ("/passage-tokens", PASSAGE_TOKENS),
    ("/comprehension-questions", COMPREHENSION_QUESTIONS),
    ("/question-choices", QUESTION_CHOICES),
)

