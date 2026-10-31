from collections.abc import Callable
from typing import Any, NoReturn

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel

from app.features.shared.models import CrudPage, ResourceDefinition
from app.features.shared.service import (
    CrudDataUnavailable,
    InvalidRecord,
    RecordConflict,
    RecordNotFound,
    ResourceCrudService,
)

ServiceDependency = Callable[..., ResourceCrudService]


def register_crud_routes(
    router: APIRouter,
    path: str,
    resource: ResourceDefinition,
    service_dependency: ServiceDependency,
) -> None:
    """Register paginated list and row CRUD routes for one resource."""
    field_summary = ", ".join(resource.create_fields)
    update_summary = ", ".join(resource.update_fields)
    create_description = (
        f"Trusted-backend create. Accepted fields: {field_summary}. "
        f"Required: {', '.join(resource.required_create_fields)}."
    )
    update_description = f"Trusted-backend partial update. Accepted fields: {update_summary}."

    def list_records(
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        service: ResourceCrudService = Depends(service_dependency),
    ) -> CrudPage:
        try:
            rows, total = service.list(resource, limit, offset)
            return CrudPage(items=rows, limit=limit, offset=offset, total=total)
        except Exception as exc:
            _raise_http_error(exc)

    def get_record(
        record_id: str,
        service: ResourceCrudService = Depends(service_dependency),
    ) -> dict[str, Any]:
        try:
            return service.get(resource, record_id)
        except Exception as exc:
            _raise_http_error(exc)

    def create_record(
        payload: BaseModel = Body(..., description=create_description),
        service: ResourceCrudService = Depends(service_dependency),
    ) -> dict[str, Any]:
        try:
            return service.create(resource, payload)
        except Exception as exc:
            _raise_http_error(exc)

    def update_record(
        record_id: str,
        payload: BaseModel = Body(..., description=update_description),
        service: ResourceCrudService = Depends(service_dependency),
    ) -> dict[str, Any]:
        try:
            return service.update(resource, record_id, payload)
        except Exception as exc:
            _raise_http_error(exc)

    def delete_record(
        record_id: str,
        service: ResourceCrudService = Depends(service_dependency),
    ) -> Response:
        try:
            service.delete(resource, record_id)
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        except Exception as exc:
            _raise_http_error(exc)

    create_record.__annotations__["payload"] = resource.create_model
    update_record.__annotations__["payload"] = resource.update_model
    base_name = resource.slug.replace("-", "_")
    router.add_api_route(
        path,
        list_records,
        methods=["GET"],
        response_model=CrudPage,
        name=f"list_{base_name}",
        summary=f"List {resource.slug}",
    )
    router.add_api_route(
        f"{path}/{{record_id}}",
        get_record,
        methods=["GET"],
        response_model=dict[str, Any],
        name=f"get_{base_name}",
        summary=f"Get {resource.model_name}",
    )
    router.add_api_route(
        path,
        create_record,
        methods=["POST"],
        response_model=dict[str, Any],
        status_code=status.HTTP_201_CREATED,
        name=f"create_{base_name}",
        summary=f"Create {resource.model_name}",
    )
    router.add_api_route(
        f"{path}/{{record_id}}",
        update_record,
        methods=["PATCH"],
        response_model=dict[str, Any],
        name=f"update_{base_name}",
        summary=f"Update {resource.model_name}",
    )
    router.add_api_route(
        f"{path}/{{record_id}}",
        delete_record,
        methods=["DELETE"],
        response_model=None,
        status_code=status.HTTP_204_NO_CONTENT,
        name=f"delete_{base_name}",
        summary=f"Delete {resource.model_name}",
    )


def _raise_http_error(exc: Exception) -> NoReturn:
    if isinstance(exc, RecordNotFound):
        raise HTTPException(status_code=404, detail="Record not found") from exc
    if isinstance(exc, InvalidRecord):
        raise HTTPException(status_code=422, detail="Record violates schema rules") from exc
    if isinstance(exc, RecordConflict):
        raise HTTPException(
            status_code=409,
            detail="Record conflicts with existing or related data",
        ) from exc
    if isinstance(exc, CrudDataUnavailable):
        raise HTTPException(
            status_code=503, detail="Database operation is unavailable"
        ) from exc
    raise exc

