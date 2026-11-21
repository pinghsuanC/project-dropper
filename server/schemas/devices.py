from uuid import UUID

from pydantic import BaseModel

from enums import PairingRequestStatus, Platform


class PairedDevice(BaseModel):
    device_id: UUID
    name: str
    platform: Platform
    paired_at: int


class PairedDeviceData(BaseModel):
    device: PairedDevice | None


class PairedDeviceResponse(BaseModel):
    message: str
    data: PairedDeviceData


class PairingStartData(BaseModel):
    pairing_request_id: str
    pairing_token: str
    expires_at: int


class PairingRequestStartResponse(BaseModel):
    message: str
    data: PairingStartData


class PairingRequestClaimResponseData(BaseModel):
    device_id: str
    name: str
    platform: Platform


class PairingRequestClaimResponseDataDict(BaseModel):
    paired_with: PairingRequestClaimResponseData


class PairingRequestClaimResponse(BaseModel):
    message: str
    data: PairingRequestClaimResponseDataDict


class PairingRequestClaim(BaseModel):
    pairing_token: str


class PairingRequstData(BaseModel):
    id: str
    status: PairingRequestStatus
    created_at: int
    expires_at: int


class GetPairingRequestResponse(BaseModel):
    message: str
    data: PairingRequstData
