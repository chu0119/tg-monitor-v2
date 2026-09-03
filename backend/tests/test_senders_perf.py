import asyncio, time
from httpx import AsyncClient
import pytest


@pytest.mark.asyncio
async def test_senders_list_under_300ms():
    async with AsyncClient(base_url="http://127.0.0.1:8000") as c:
        t0 = time.perf_counter()
        r = await c.get("/api/v1/senders?limit=20")
        elapsed = (time.perf_counter() - t0) * 1000
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"][0]["alert_count"], int)
        assert elapsed < 300, f"senders list took {elapsed:.0f}ms"
