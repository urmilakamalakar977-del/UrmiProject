FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && addgroup --system app \
    && adduser --system --ingroup app app \
    && mkdir -p /app/data /app/media /app/staticfiles \
    && chown -R app:app /app

COPY --chown=app:app . .

USER app

EXPOSE 8000

CMD ["gunicorn", "ecom.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
