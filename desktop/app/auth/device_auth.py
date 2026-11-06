from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

PRIVATE_KEY_FILE = "../device_key.pem"


class DeviceAuth:
    def __init__(self):
        # load or create on start up
        self.key_path = Path(PRIVATE_KEY_FILE)
        self.private_key = self._load_or_create_private_key_pem()

    def _load_or_create_private_key_pem(self) -> str:
        # private key is stored in a file, if it doesn't exist, generate a new one and save it

        # Load from file if it exists
        if self.key_path.is_file():
            return serialization.load_pem_private_key(
                self.key_path.read_bytes(), password=None
            )

        # Generate a new Ed25519 private key
        private_key = Ed25519PrivateKey.generate()
        self.key_path.write_bytes(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        return private_key

    def get_public_key_pem(self) -> str:

        # Get the public key from the private key
        public_key = self.private_key.public_key()

        # Serialize the public key to PEM format
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        return public_pem

    def sign(self, challenge: bytes) -> bytes:
        return self.private_key.sign(challenge)
