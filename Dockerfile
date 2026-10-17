FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CRYPTO_ALARM_HOST=0.0.0.0 \
    CRYPTO_ALARM_DATA=/data/crypto_data_binance.json \
    CRYPTO_ALARM_LOG_JSON=1

WORKDIR /app

# Dependencies first so this layer is cached until requirements.lock changes.
COPY requirements.lock .
RUN pip install -r requirements.lock

COPY pyproject.toml README.md ./
COPY crypto_alarm ./crypto_alarm
RUN pip install --no-deps . \
    && useradd --system --no-create-home app \
    && mkdir /data && chown app /data

USER app
VOLUME /data
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/healthz', timeout=3)"

# One worker only: pairs, alarms and price history live in this process.
CMD ["gunicorn", "--worker-class", "gthread", "--workers", "1", "--threads", "100", \
     "--bind", "0.0.0.0:5000", "crypto_alarm.web:create_app()"]
