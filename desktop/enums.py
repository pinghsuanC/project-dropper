from enum import StrEnum


class DeviceStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class Platform(StrEnum):
    DESKTOP = "desktop"
    ANDROID = "android"
    IOS = "ios"
