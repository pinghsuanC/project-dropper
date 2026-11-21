from enum import StrEnum


class DeviceStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class Platform(StrEnum):
    DESKTOP = "desktop"
    ANDROID = "android"
    IOS = "ios"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class PairingRequestStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class FileStatus(StrEnum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    DELETED = "deleted"
    DOWNLOADED = "downloaded"


class DevicePairStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
