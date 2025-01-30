FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1
ENV POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

RUN mkdir -p /app
WORKDIR /app

RUN apt-get update
RUN pip install poetry
COPY poetry.lock pyproject.toml /app/
RUN poetry install --without dev,test --no-root


FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"
ENV BOT_TOKEN=${BOT_TOKEN} \
    ANTHROPIC_TOKEN=${ANTHROPIC_TOKEN} \
    ELEVENLABS_TOKEN=${ELEVENLABS_TOKEN} \
    SD_SERVER_URL=${SD_SERVER_URL} \
    LLM_SERVER_URL=${LLM_SERVER_URL} \
    REDIS_DEFAULTS=${REDIS_DEFAULTS}

COPY --from=builder /app /app

WORKDIR /app
COPY main.py redis-init.sh /app/

CMD ["python", "main.py"]
