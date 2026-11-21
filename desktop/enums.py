from enum import StrEnum


class AppEnv(StrEnum):
    LOCAL = "local"
    DEV = "dev"
    PROD = "prod"


class DeviceStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class Platform(StrEnum):
    DESKTOP = "desktop"
    ANDROID = "android"
    IOS = "ios"


class PairingStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
