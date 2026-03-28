import uuid

from pydantic import BaseModel


class WorkspaceOut(BaseModel):
    id: uuid.UUID
    name: str
    role: str
