from uuid import UUID

from pydantic import BaseModel

from enums import Platform


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
