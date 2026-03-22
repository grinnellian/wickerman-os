FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir nicegui docker psutil nvidia-ml-py requests
RUN git config --global --add safe.directory /app     && git config --global --add safe.directory /support     && git config --global user.name "Wickerman OS"     && git config --global user.email "wickerman@local"
WORKDIR /app
HEALTHCHECK --interval=15s --timeout=5s --retries=3 CMD curl -sf http://localhost:8000 || exit 1
CMD ["python3", "core_app/main.py"]
