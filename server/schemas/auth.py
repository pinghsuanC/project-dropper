from pydantic import BaseModel

from enums import Platform


class MeData(BaseModel):
    device_id: str
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
    device_id: str


class ChallengeVerifyRequest(BaseModel):
    device_id: str
    challenge: str
    signature: str
