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
RUN poetry install --without dev,test


FROM python:3.10-slim as base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"
ENV BOT_TOKEN=${BOT_TOKEN} \
    CHAT_ID=${CHAT_ID} \
    SD_SERVER_URL=${SD_SERVER_URL}

COPY --from=builder /app /app
# RUN adduser myuser && chown -R myuser /app
# USER myuser

WORKDIR /app
COPY main.py /app/

CMD ["python", "main.py"]
