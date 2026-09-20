import httpx


async def test_health_over_real_http(live_server: str) -> None:
    async with httpx.AsyncClient(base_url=live_server) as http_client:
        response = await http_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
