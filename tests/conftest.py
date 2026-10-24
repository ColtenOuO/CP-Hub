import os

import pytest
from sqlalchemy.engine import make_url

# Tests create and delete real rows (including the single active group task), so they must never touch the bot's database.
# They only run against TEST_DATABASE_URL, which must name a disposable database containing "test", and it overrides
# DATABASE_URL for the whole run. This has to happen before anything imports backend.app.core.config.
_test_database_url = os.environ.get("TEST_DATABASE_URL", "")
if not _test_database_url or "test" not in (make_url(_test_database_url).database or ""):
    pytest.exit(
        "Refusing to run tests: set TEST_DATABASE_URL to a disposable database whose name contains 'test' "
        "(e.g. postgresql+asyncpg://cphub:cphub@localhost:5432/cphub_test). Tests delete data.",
        returncode=4,
    )

os.environ["DATABASE_URL"] = _test_database_url
