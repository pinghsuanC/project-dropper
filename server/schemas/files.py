from uuid import UUID

from pydantic import BaseModel, Field


class PrepareUploadRequest(BaseModel):
    file_name: str
    size: int
    content_type: str
    checksum: str
    receiver_id: UUID


class FinishUploadRequest(BaseModel):
    file_id: UUID


class FinishDownloadRequest(BaseModel):
    file_ids: list[UUID] = Field(min_length=1, max_length=100)
