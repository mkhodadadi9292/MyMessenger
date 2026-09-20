from httpx import AsyncClient

from tests.fakes import CapturingOtpSender

API_V1 = "/api/v1"


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def request_otp(client: AsyncClient, identifier: str) -> dict:
    response = await client.post(f"{API_V1}/auth/otp/request", json={"identifier": identifier})
    assert response.status_code == 200, response.text
    return response.json()


async def verify_otp(client: AsyncClient, identifier: str, code: str) -> dict:
    response = await client.post(
        f"{API_V1}/auth/otp/verify", json={"identifier": identifier, "code": code}
    )
    assert response.status_code == 200, response.text
    return response.json()


async def register_user(
    client: AsyncClient,
    otp_sender: CapturingOtpSender,
    identifier: str,
    username: str,
    first_name: str,
    last_name: str | None = None,
) -> dict:
    """Full A1→A2→A3 register flow. Returns {access_token, refresh_token, user}."""
    await request_otp(client, identifier)
    verified = await verify_otp(client, identifier, otp_sender.code_for(identifier))
    assert verified.get("registered") is False
    payload: dict = {
        "registration_token": verified["registration_token"],
        "username": username,
        "first_name": first_name,
    }
    if last_name is not None:
        payload["last_name"] = last_name
    response = await client.post(f"{API_V1}/auth/register", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


async def login_user(
    client: AsyncClient, otp_sender: CapturingOtpSender, identifier: str
) -> dict:
    """Full A1→A2 login flow for an existing user. Returns {access_token, refresh_token, user}."""
    await request_otp(client, identifier)
    verified = await verify_otp(client, identifier, otp_sender.code_for(identifier))
    assert "access_token" in verified
    return verified
