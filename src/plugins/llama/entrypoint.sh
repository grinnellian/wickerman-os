#!/bin/bash
set -e
MODEL_DIR=${MODEL_DIR:-/models}
GPU_LAYERS=${GPU_LAYERS:-99}
CTX_SIZE=${CTX_SIZE:-4096}
HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8080}
BUILD_MARKER=/data/.build_done
BUILD_LOG=/data/build.log

echo "============================================"
echo "  WICKERMAN LLAMA SERVER — Hardware Detect"
echo "============================================"

CPU_FLAGS=$(cat /proc/cpuinfo | grep flags | head -1)
CMAKE_ARGS=""
if echo "$CPU_FLAGS" | grep -q 'avx2'; then
    echo "[CPU] AVX2 detected"; CMAKE_ARGS="$CMAKE_ARGS -DGGML_AVX2=ON"
elif echo "$CPU_FLAGS" | grep -q 'avx'; then
    echo "[CPU] AVX only (no AVX2)"; CMAKE_ARGS="$CMAKE_ARGS -DGGML_AVX2=OFF -DGGML_AVX=ON"
else
    echo "[CPU] No AVX — SSE3 fallback"; CMAKE_ARGS="$CMAKE_ARGS -DGGML_AVX2=OFF -DGGML_AVX=OFF"
fi

if nvidia-smi &>/dev/null; then
    echo "[GPU] NVIDIA detected — enabling CUDA"
    CMAKE_ARGS="$CMAKE_ARGS -DGGML_CUDA=ON"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
else
    echo "[GPU] No NVIDIA GPU — CPU only"; CMAKE_ARGS="$CMAKE_ARGS -DGGML_CUDA=OFF"; GPU_LAYERS=0
fi

BUILD_VER=2
if [ ! -f "$BUILD_MARKER" ] || [ ! -f "/data/llama-server" ] || [ "$(cat $BUILD_MARKER 2>/dev/null)" != "$BUILD_VER" ]; then
    echo "[BUILD] Compiling llama.cpp (first run only — cached after this)..."
    echo "[BUILD] FLAGS: $CMAKE_ARGS"
    cd /opt/llama.cpp && rm -rf build && mkdir build && cd build
    cmake .. $CMAKE_ARGS -DLLAMA_CURL=ON 2>&1 | tee $BUILD_LOG
    cmake --build . --config Release -j$(nproc) 2>&1 | tee -a $BUILD_LOG
    cp bin/llama-server /data/llama-server 2>/dev/null || \
    cp bin/server /data/llama-server 2>/dev/null || \
    { echo "[ERROR] Server binary not found"; ls -la bin/; exit 1; }
    chmod +x /data/llama-server
    # Copy shared libraries that llama-server links against
    mkdir -p /data/lib
    cp -a lib/*.so* /data/lib/ 2>/dev/null || cp -a bin/*.so* /data/lib/ 2>/dev/null || true
    echo "$BUILD_VER" > "$BUILD_MARKER"
    echo "[BUILD] Done!"
else
    echo "[BUILD] Using cached build"
fi
cp /data/llama-server /usr/local/bin/llama-server
chmod +x /usr/local/bin/llama-server
# Install shared libraries so the linker finds them
if [ -d /data/lib ] && ls /data/lib/*.so* &>/dev/null; then
    cp -a /data/lib/*.so* /usr/local/lib/
    ldconfig
    echo "[BUILD] Shared libraries installed"
fi

mkdir -p /opt/llama.cpp/examples/server/public
cp /opt/test_chat.html /opt/llama.cpp/examples/server/public/index.html

# List available models
MODEL_COUNT=$(ls $MODEL_DIR/*.gguf 2>/dev/null | wc -l)
echo "[MODEL] $MODEL_COUNT model(s) in $MODEL_DIR"
ls -lh $MODEL_DIR/*.gguf 2>/dev/null || echo "[MODEL] No models found — add GGUFs to ~/aidojo/models/ and reinstall"

echo ""
echo "Starting Wickerman Model Router (multi-model + unified API)"
echo "  Models dir: $MODEL_DIR"
echo "  GPU layers: $GPU_LAYERS | Context: $CTX_SIZE"
exec python3 /opt/manager.py
