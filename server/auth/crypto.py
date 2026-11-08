import base64
import hashlib
import hmac
import os
import secrets

import dotenv
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import HTTPException

from exceptions import InvalidPublicKey, InvalidSignature

dotenv.load_dotenv()
HMAC_SECRET = os.getenv("HMAC_SECRET")


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify_signature(device_public_key, challenge, signature) -> bool:
    # load public key stored on the device table
    public_key = serialization.load_pem_public_key(device_public_key.encode())

    try:
        public_key.verify(
            base64.b64decode(signature),  # signature: base64 text → raw bytes
            challenge.encode(),  # the exact bytes the desktop signed
        )

    except InvalidSignature:
        raise HTTPException(status_code=401, detail="Invalid challenge or signature")

    return True


def geenrate_challenge() -> str:
    return base64.b64encode(secrets.token_bytes(32)).decode()


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
