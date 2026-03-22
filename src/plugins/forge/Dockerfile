FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git nodejs npm zip && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir flask==3.0.* requests==2.32.* gunicorn==22.*
RUN useradd -m -s /bin/bash forgeuser
WORKDIR /app
ARG CACHEBUST=1
COPY . .
RUN chown -R forgeuser:forgeuser /app
USER forgeuser
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "120", "app:app"]
