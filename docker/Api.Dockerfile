FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENV GODS_EYE_DATASET_ROOT=/app/app/modules/ai_gods_eye_view/package/source/social_networks/v1
COPY apps/backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY apps/backend/app ./app
COPY scripts/deployment ./scripts/deployment
RUN mkdir -p /var/lib/gods-eye-view && chown 65534:65534 /var/lib/gods-eye-view
USER 65534:65534
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--proxy-headers", "--forwarded-allow-ips", "*"]
