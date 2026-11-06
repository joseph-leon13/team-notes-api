"""Request and response schemas for notes."""

from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from team_notes_api.schemas.common import RequestModel, UTCTimestamp

MAX_TAGS = 20
MAX_TAG_LENGTH = 32

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Body = Annotated[str, Field(max_length=100_000)]
Tags = Annotated[list[str], Field(max_length=MAX_TAGS)]


def normalize_tags(tags: list[str]) -> list[str]:
    """Strip, lower-case and de-duplicate tags (first occurrence wins), validating length."""
    normalized: list[str] = []
    for raw in tags:
        tag = raw.strip().lower()
        if not 1 <= len(tag) <= MAX_TAG_LENGTH:
            raise ValueError(f"each tag must be 1-{MAX_TAG_LENGTH} characters after trimming")
        if tag not in normalized:
            normalized.append(tag)
    return normalized


class NoteCreate(RequestModel):
    """Body of ``POST /teams/{team_id}/notes``."""

    title: Title
    body: Body = ""
    tags: Tags = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, value: list[str]) -> list[str]:
        return normalize_tags(value)


class NoteUpdate(RequestModel):
    """Body of ``PATCH /notes/{note_id}``.

    ``version`` is the version the client last read; the edit only applies if it is
    still current. At least one editable field must be present, and none may be null.
    """

    version: int = Field(ge=1)
    title: Title | None = None
    body: Body | None = None
    tags: Tags | None = None

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        return normalize_tags(value) if value is not None else None

    @model_validator(mode="after")
    def _require_an_editable_field(self) -> "NoteUpdate":
        editable = self.model_fields_set & {"title", "body", "tags"}
        if not editable:
            raise ValueError("provide at least one of: title, body, tags")
        for field in editable:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self

    def changes(self) -> dict[str, Any]:
        """Return the editable fields the client actually sent."""
        return {field: getattr(self, field) for field in self.model_fields_set - {"version"}}


class NoteOut(BaseModel):
    """A note as returned by the API. ``tags`` are sorted."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    title: str
    body: str
    tags: list[str]
    version: int
    created_by_id: int
    updated_by_id: int
    created_at: UTCTimestamp
    updated_at: UTCTimestamp

    @field_validator("tags", mode="before")
    @classmethod
    def _tag_names(cls, value: list[Any]) -> list[str]:
        """Accept ORM tag rows (anything with a ``.tag``) as well as plain strings."""
        return sorted(getattr(item, "tag", item) for item in value)
