from fastapi import Cookie, HTTPException
from .token_validator import TokenValidator, TokenValidationError


async def get_current_user(access_token: str = Cookie(None)):
    if access_token is None:
        raise HTTPException(status_code=401, detail="Missing token")

    validator = TokenValidator()

    try:
        payload = validator.validate(access_token)
    except TokenValidationError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return payload
    