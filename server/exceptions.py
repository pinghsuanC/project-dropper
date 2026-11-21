class InvalidPublicKey(Exception):
    pass


class DeviceNotExist(Exception):
    pass


class DeviceAlreadyExists(Exception):
    pass


class ChallengeAlreadyExists(Exception):
    pass


class PairingRequestAlreadyUsedError(Exception):
    """The pairing request was claimed, expired, or removed before this claim could finish."""
