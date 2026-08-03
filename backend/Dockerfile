FROM python:3.12.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_PROGRESS=1

RUN python -m pip install --no-cache-dir uv==0.12.1

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src

EXPOSE 8000

CMD ["uv", "run", "--no-dev", "uvicorn", "atlas.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
