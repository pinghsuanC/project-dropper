from typing import Literal, TypedDict
from uuid import UUID

from pydantic import BaseModel, Field


class PrepareUploadRequest(BaseModel):
    file_name: str
    size: int
    content_type: str
    checksum: str
    receiver_id: UUID


class FileInfo(TypedDict):
    file_name: str
    size: int
    content_type: str
    checksum: str
    client_ref: str


class PrepareBatchUploadRequest(BaseModel):
    receiver_id: UUID
    files: list[FileInfo] = Field(min_length=1, max_length=20)


class FinishUploadRequest(BaseModel):
    file_id: UUID


class FinishBatchUploadRequest(BaseModel):
    file_ids: list[UUID] = Field(min_length=1, max_length=100)


class FinishDownloadRequest(BaseModel):
    file_ids: list[UUID] = Field(min_length=1, max_length=100)


class SentFile(BaseModel):
    file_id: UUID
    file_name: str
    size: int
    status: Literal["pending", "uploaded"]
    receiver_name: str
    created_at: int


class SentFilesResponse(BaseModel):
    message: str
    data: list[SentFile]
