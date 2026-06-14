import pytest

from backend.app.core.db import engine


@pytest.fixture(autouse=True)
async def _dispose_engine_pool():
    yield
    await engine.dispose()
