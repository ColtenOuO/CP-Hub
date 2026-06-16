#!/bin/sh
uv run alembic upgrade head
exec uv run python -m bot.main
