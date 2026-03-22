"""Wickerman OS v5.2.0 — Chat plugin manifest."""
from pathlib import Path

_FILES_DIR = Path(__file__).parent.parent / "src" / "plugins" / "chat"

PLUGIN_HOST = ("127.0.0.1", "chat.wickerman.local")

WM_CHAT = {'name': 'Chat', 'description': 'Conversation UI for Wickerman agents', 'icon': 'chat', 'build': True, 'build_context': 'data', 'container_name': 'wm-chat', 'url': 'http://chat.wickerman.local', 'ports': [5000], 'gpu': False, 'env': ['LLAMA_API=http://wm-llama:8080'], 'volumes': ['{self}/app_data:/data'], 'nginx_host': 'chat.wickerman.local', 'help': '## Chat\nConversation UI for Wickerman agents.\n\n**Agents** are configured in the Model Router (system prompt, RAG, settings).\nChat just picks an agent and manages conversation history.\n\n**Node API:** `/node/schema` and `/node/execute` for wm-flow integration.'}

WM_CHAT_FILES = {
    "data/Dockerfile": (_FILES_DIR / "Dockerfile").read_text(),
    "data/app.py": (_FILES_DIR / "app.py").read_text(),
    "data/templates/index.html": (_FILES_DIR / "templates" / "index.html").read_text(),
}

WM_CHAT["files"] = WM_CHAT_FILES
