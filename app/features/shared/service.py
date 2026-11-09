import logging
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel

from app.features.shared.models import ResourceDefinition
from app.features.shared.repository import SupabaseCrudRepository

logger = logging.getLogger(__name__)
T = TypeVar("T")


class RecordNotFound(Exception):
    """The requested row does not exist."""


class InvalidRecord(Exception):
    """The row violates a database constraint or payload rule."""


class RecordConflict(Exception):
    """The row conflicts with an existing row or related data."""


class CrudDataUnavailable(Exception):
    """The database operation could not be completed."""


class ResourceCrudService:
    """Validates write fields and coordinates generic resource persistence."""

    def __init__(self, repository: SupabaseCrudRepository) -> None:
        self._repository = repository

    def list(
        self, resource: ResourceDefinition, limit: int, offset: int
    ) -> tuple[list[dict[str, Any]], int | None]:
        return self._run(lambda: self._repository.list(resource, limit, offset))

    def get(self, resource: ResourceDefinition, record_id: str) -> dict[str, Any]:
        record = self._run(lambda: self._repository.get(resource, record_id))
        if record is None:
            raise RecordNotFound
        return record

    def create(
        self, resource: ResourceDefinition, payload: BaseModel
    ) -> dict[str, Any]:
        values = payload.model_dump(mode="json", exclude_unset=True)
        record = self._run(lambda: self._repository.create(resource, values))
        if record is None:
            raise CrudDataUnavailable
        return record

    def update(
        self, resource: ResourceDefinition, record_id: str, payload: BaseModel
    ) -> dict[str, Any]:
        values = payload.model_dump(mode="json", exclude_unset=True)
        if not values:
            raise InvalidRecord("At least one update field is required")
        record = self._run(
            lambda: self._repository.update(resource, record_id, values)
        )
        if record is None:
            raise RecordNotFound
        return record

    def delete(self, resource: ResourceDefinition, record_id: str) -> None:
        deleted = self._run(lambda: self._repository.delete(resource, record_id))
        if not deleted:
            raise RecordNotFound

    @staticmethod
    def _run(operation: Callable[[], T]) -> T:
        try:
            return operation()
        except (RecordNotFound, InvalidRecord, RecordConflict, CrudDataUnavailable):
            raise
        except Exception as exc:
            code = str(getattr(exc, "code", ""))
            if code in {"23505", "23503"}:
                raise RecordConflict from exc
            if code in {"23502", "23514", "22P02", "22003", "22001", "P0001"}:
                raise InvalidRecord from exc
            logger.exception("Feature API database operation failed")
            raise CrudDataUnavailable from exc

