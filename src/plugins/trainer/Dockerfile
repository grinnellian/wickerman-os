FROM nvidia/cuda:12.2.0-devel-ubuntu22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-dev git curl build-essential && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir flask==3.0.* gunicorn==22.* requests==2.32.*
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cu121
RUN pip install --no-cache-dir "unsloth[cu121-torch240] @ git+https://github.com/unslothai/unsloth.git"
RUN pip install --no-cache-dir datasets transformers trl peft accelerate bitsandbytes
WORKDIR /app
ARG CACHEBUST=1
COPY . .
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "2", "--timeout", "0", "app:app"]
