from typing import Annotated

from fastapi import (
    Depends,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import repositories.session as session_repo
from auth import crypto

bearer = HTTPBearer()


def get_current_session(
    creds: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
) -> dict:
    if creds.credentials is None:
        return None
    # hash it → find active, unexpired session → load device → or raise 401
    token_hashed = crypto.hash_session_token(creds.credentials)
    session = session_repo.get_device_active_session(token_hashed)
    return session


CurrentSession = Annotated[dict, Depends(get_current_session)]
