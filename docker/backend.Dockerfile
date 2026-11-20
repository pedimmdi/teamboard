FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

COPY config/ .

RUN groupadd --gid 10001 teamboard \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin teamboard \
    && mkdir -p /app/media /app/private_attachments /app/private_chat_attachments \
    && chown -R 10001:10001 /app

USER 10001:10001

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
