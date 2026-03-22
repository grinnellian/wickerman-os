"""Wickerman OS v5.2.0 — Model Router plugin manifest."""
from pathlib import Path

_FILES_DIR = Path(__file__).parent.parent / "src" / "plugins" / "llama"

PLUGIN_HOST = ("127.0.0.1", "llama.wickerman.local")

WM_LLAMA = {'name': 'Model Router', 'description': 'Agent orchestration with local models, remote APIs, and RAG', 'icon': 'hub', 'build': True, 'build_context': 'data', 'container_name': 'wm-llama', 'url': 'http://llama.wickerman.local', 'ports': [8080], 'gpu': True, 'env': ['MODEL_DIR=/models', 'GPU_LAYERS=99', 'CTX_SIZE=4096', 'HOST=0.0.0.0', 'PORT=8080'], 'volumes': ['{models}:/models', '{self}/data:/data'], 'nginx_host': 'llama.wickerman.local', 'help': '## Model Router\nAgent orchestration layer: local models + remote APIs + RAG + system prompts.\n\n**API:** `http://wm-llama:8080/v1/chat/completions` (OpenAI-compatible)\n\n**Multi-model:** Load/unload models independently, each on its own port.\n\n**Settings:** Context size, GPU layers, KV cache quantization, RoPE, flash attention, and more.\n\n**Models:** Add GGUFs to ~/aidojo/models/ and reinstall, or use the Downloader.'}

WM_LLAMA_FILES = {
    "data/Dockerfile": (_FILES_DIR / "Dockerfile").read_text(),
    "data/entrypoint.sh": (_FILES_DIR / "entrypoint.sh").read_text(),
    "data/test_chat.html": (_FILES_DIR / "test_chat.html").read_text(),
    "data/manager.py": (_FILES_DIR / "manager.py").read_text(),
}

WM_LLAMA["files"] = WM_LLAMA_FILES
