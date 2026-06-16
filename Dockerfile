FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY . .

RUN uv sync --frozen --no-dev

RUN chmod +x entrypoint.sh

CMD ["./entrypoint.sh"]
