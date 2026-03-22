"""
Wickerman OS v5.2.0 — Embedded file contents.
Imported by wickermaninstall.py. Place this file next to the installer.
"""
from pathlib import Path

_HERE = Path(__file__).parent

# ══════════════════════════════════════════════════════════════════════════════
#  CORE DASHBOARD — runs inside wm-core container
# ══════════════════════════════════════════════════════════════════════════════

MAIN_PY = (_HERE / "src" / "core" / "main.py").read_text()

# ══════════════════════════════════════════════════════════════════════════════
#  CORE DOCKERFILE
# ══════════════════════════════════════════════════════════════════════════════

CORE_DOCKERFILE = (_HERE / "src" / "core" / "Dockerfile").read_text()

# ══════════════════════════════════════════════════════════════════════════════
#  HUGGINGFACE DOWNLOADER — Flask app (replaces old raw-URL downloader)
# ══════════════════════════════════════════════════════════════════════════════

DOWNLOADER_APP_PY = (_HERE / "src" / "downloader" / "app.py").read_text()

DOWNLOADER_INDEX_HTML = (_HERE / "src" / "downloader" / "templates" / "index.html").read_text()

# ══════════════════════════════════════════════════════════════════════════════
#  DOWNLOADER DOCKERFILE & REQUIREMENTS
# ══════════════════════════════════════════════════════════════════════════════

DOWNLOADER_REQUIREMENTS = (_HERE / "src" / "downloader" / "requirements.txt").read_text()

DOWNLOADER_DOCKERFILE = (_HERE / "src" / "downloader" / "Dockerfile").read_text()

# ══════════════════════════════════════════════════════════════════════════════
#  NGINX CONFIG GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

GENERATE_NGINX_PY = (_HERE / "src" / "nginx" / "generate_nginx.py").read_text()
