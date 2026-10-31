from typing import Any

from supabase import Client

from app.features.shared.models import ResourceDefinition


class SupabaseCrudRepository:
    """Performs one resource's persistence operations through Supabase."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def list(
        self, resource: ResourceDefinition, limit: int, offset: int
    ) -> tuple[list[dict[str, Any]], int | None]:
        response = (
            self._client.table(resource.table)
            .select("*", count="exact")
            .order(resource.primary_key)
            .range(offset, offset + limit - 1)
            .execute()
        )
        data = response.data if isinstance(response.data, list) else []
        rows = [row for row in data if isinstance(row, dict)]
        return rows, response.count

    def get(self, resource: ResourceDefinition, record_id: str) -> dict[str, Any] | None:
        response = (
            self._client.table(resource.table)
            .select("*")
            .eq(resource.primary_key, record_id)
            .maybe_single()
            .execute()
        )
        return response.data if isinstance(response.data, dict) else None

    def create(
        self, resource: ResourceDefinition, values: dict[str, Any]
    ) -> dict[str, Any] | None:
        response = (
            self._client.table(resource.table)
            .insert(values)
            .select("*")
            .single()
            .execute()
        )
        return response.data if isinstance(response.data, dict) else None

    def update(
        self,
        resource: ResourceDefinition,
        record_id: str,
        values: dict[str, Any],
    ) -> dict[str, Any] | None:
        response = (
            self._client.table(resource.table)
            .update(values)
            .eq(resource.primary_key, record_id)
            .select("*")
            .maybe_single()
            .execute()
        )
        return response.data if isinstance(response.data, dict) else None

    def delete(self, resource: ResourceDefinition, record_id: str) -> bool:
        existing = (
            self._client.table(resource.table)
            .select(resource.primary_key)
            .eq(resource.primary_key, record_id)
            .maybe_single()
            .execute()
        )
        if not isinstance(existing.data, dict):
            return False
        self._client.table(resource.table).delete().eq(
            resource.primary_key, record_id
        ).execute()
        return True

