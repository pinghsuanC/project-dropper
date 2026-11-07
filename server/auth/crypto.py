import hashlib
import hmac
import os

import dotenv
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from exceptions import InvalidPublicKey

dotenv.load_dotenv()
HMAC_SECRET = os.getenv("HMAC_SECRET")


def load_ed25519_public_key(pem: str) -> Ed25519PublicKey:
    try:
        key = serialization.load_pem_public_key(pem.encode())
    except (ValueError, UnsupportedAlgorithm) as e:
        raise InvalidPublicKey("Not a valid PEM public key") from e

    if not isinstance(key, Ed25519PublicKey):
        raise InvalidPublicKey(status_code=400, detail="Public key must be Ed25519")

    canonical_pem = key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()  # str: for the database

    return canonical_pem


def hash_input(input: str) -> str:
    return hmac.new(
        HMAC_SECRET.encode(),  # key, as bytes
        input.encode(),  # message, as bytes
        hashlib.sha256,  # algorithm
    ).hexdigest()
