FROM python:3.12-slim

WORKDIR /app

ENV PYTHONPATH=/app

COPY apps/api /app/apps/api
COPY services /app/services
COPY packages /app/packages
RUN pip install --no-cache-dir -e /app/apps/api[dev]

WORKDIR /app/apps/api
CMD ["uvicorn", "polymarket_trader.main:app", "--host", "0.0.0.0", "--port", "8000"]
