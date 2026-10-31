from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, create_model


class CrudPage(BaseModel):
    """A page of rows returned by a collection endpoint."""

    items: list[dict[str, Any]]
    limit: int
    offset: int
    total: int | None = None


@dataclass(frozen=True)
class ResourceDefinition:
    """Database resource metadata and its generated request models."""

    model_name: str
    slug: str
    table: str
    primary_key: str
    field_types: dict[str, Any]
    create_fields: tuple[str, ...]
    required_create_fields: tuple[str, ...]
    update_fields: tuple[str, ...]
    create_model: type[BaseModel] = field(init=False, repr=False)
    update_model: type[BaseModel] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        create_model_fields = {
            name: (
                self.field_types[name],
                Field(... if name in self.required_create_fields else None),
            )
            for name in self.create_fields
        }
        update_model_fields = {
            name: (self.field_types[name], None) for name in self.update_fields
        }
        model_config = ConfigDict(extra="forbid")
        object.__setattr__(
            self,
            "create_model",
            create_model(
                f"{self.model_name}Create",
                __config__=model_config,
                **create_model_fields,
            ),
        )
        object.__setattr__(
            self,
            "update_model",
            create_model(
                f"{self.model_name}Update",
                __config__=model_config,
                **update_model_fields,
            ),
        )

