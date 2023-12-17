FROM python:3.10-slim as builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1
ENV POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

RUN mkdir -p /app
WORKDIR /app

RUN pip install poetry
COPY poetry.lock pyproject.toml /app/
RUN poetry install --without dev


FROM python:3.10-slim as base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

COPY --from=builder /app /app
WORKDIR /app

COPY main.py .env /app/
COPY src/ /app/src/
RUN mkdir /app/logs

USER daemon
CMD ["poetry", "run python", "main.py"]
