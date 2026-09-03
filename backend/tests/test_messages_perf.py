import asyncio, time
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_messages_list_under_300ms():
    async with AsyncClient(base_url="http://127.0.0.1:8000") as c:
        t0 = time.perf_counter()
        r = await c.get("/api/v1/messages?limit=50")
        elapsed = (time.perf_counter() - t0) * 1000
        assert r.status_code == 200
        assert elapsed < 300, f"messages list took {elapsed:.0f}ms"
