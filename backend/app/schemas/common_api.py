"""Shared API body models (strict empty JSON for no-payload POST handlers)."""

from pydantic import BaseModel, ConfigDict


class EmptyJSONBody(BaseModel):
    """Use for POST endpoints with no fields: body must be ``{}`` or omitted (see endpoint)."""

    model_config = ConfigDict(extra="forbid")
