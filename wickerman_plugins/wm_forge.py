"""Wickerman OS v5.2.0 — Code Forge plugin manifest."""
from pathlib import Path

_FILES_DIR = Path(__file__).parent.parent / "src" / "plugins" / "forge"

PLUGIN_HOST = ("127.0.0.1", "forge.wickerman.local")

WM_FORGE = {'name': 'Code Forge', 'description': 'AI-assisted code sandbox — write, run, and export apps', 'icon': 'construction', 'build': True, 'build_context': 'data', 'container_name': 'wm-forge', 'url': 'http://forge.wickerman.local', 'ports': [5000], 'gpu': False, 'network': 'wm-forge-net', 'env': ['LLAMA_API=http://wm-llama:8080', 'WORKSPACE=/workspace'], 'volumes': ['{self}/data:/data', '{workspace}:/workspace', '{models}:/models'], 'nginx_host': 'forge.wickerman.local', 'help': '## Code Forge\nAI-assisted code creation and execution sandbox.\n\n**Standalone:** Describe what you want, the AI writes code, you run it, iterate, export.\n\n**As a node:** POST `/node/execute` with `{"instruction": "...", "language": "python"}` to generate and run code.\n\n**Export:** Package projects as zip files or standalone installers.\n\n**Workspace:** Files saved to `~/wickerman/workspace/` persist across sessions.'}

WM_FORGE_FILES = {
    "data/Dockerfile": (_FILES_DIR / "Dockerfile").read_text(),
    "data/app.py": (_FILES_DIR / "app.py").read_text(),
    "data/templates/index.html": (_FILES_DIR / "templates" / "index.html").read_text(),
}

WM_FORGE["files"] = WM_FORGE_FILES
