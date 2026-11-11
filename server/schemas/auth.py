from uuid import UUID

from pydantic import BaseModel

from enums import Platform


class MeData(BaseModel):
    device_id: UUID
    name: str
    platform: str


class MeResponse(BaseModel):
    message: str
    data: MeData


class RegisterRequest(BaseModel):
    name: str
    public_key: str
    platform: Platform
    fingerprint: str


class ChallengeRequest(BaseModel):
    device_id: UUID


class ChallengeVerifyRequest(BaseModel):
    device_id: UUID
    challenge: str
    signature: str
