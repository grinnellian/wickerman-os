FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir flask==3.0.* requests==2.32.* gunicorn==22.*
WORKDIR /app
ARG CACHEBUST=1
COPY . .
EXPOSE 5000
HEALTHCHECK --interval=10s --timeout=3s CMD curl -sf http://localhost:5000/health || exit 1
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "300", "app:app"]
