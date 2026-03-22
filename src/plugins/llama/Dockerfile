FROM nvidia/cuda:12.2.0-devel-ubuntu22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git curl python3 python3-pip ca-certificates python3-dev \
    && rm -rf /var/lib/apt/lists/*
RUN pip3 install --no-cache-dir faiss-cpu numpy tiktoken nvidia-ml-py
RUN git clone --depth 1 https://github.com/ggerganov/llama.cpp /opt/llama.cpp
WORKDIR /opt/llama.cpp
ARG CACHEBUST=1
COPY entrypoint.sh /entrypoint.sh
COPY test_chat.html /opt/test_chat.html
COPY manager.py /opt/manager.py
RUN chmod +x /entrypoint.sh
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=5s --start-period=300s --retries=3 CMD curl -sf http://localhost:8080/health || exit 1
ENTRYPOINT ["/entrypoint.sh"]
