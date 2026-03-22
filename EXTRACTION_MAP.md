# EXTRACTION MAP

Blueprint for extracting all embedded source code from string constants into real files.

Generated: 2026-03-21 | Wickerman OS v5.2.0

---

## 1. How the Installer Works

### Write Flow

`wickermaninstall.py` calls `write_file(path, content)` to write embedded constants to disk.
The install directory is `~/wickerman/` (variable `INSTALL_DIR`).
The support directory is `~/WickermanSupport/` (variable `SUPPORT_DIR`).

Three categories of output:

| Category | Source | How Written |
|----------|--------|-------------|
| **Embedded constants** | `wickerman_support.py` variables | `write_file(INSTALL_DIR / "...", CONSTANT)` |
| **Plugin manifests** | `wickerman_plugins/*.py` dicts | `write_file(SUPPORT_DIR / "plugins/" / fname, json.dumps(manifest))` |
| **Dynamically generated** | Built in `main()` at runtime | `write_file(INSTALL_DIR / "...", f-string)` |

### Plugin File Extraction (runtime, not at install)

Plugin files (the `"files"` dict inside each manifest) are NOT written by the installer.
They are extracted at runtime by the dashboard (`main.py` inside `wm-core`) during `_install_task()`:

```python
for fn, fc in manifest["files"].items():
    fp = os.path.join(f"/support/plugins/{pid}", fn)
    with open(fp, "w") as f: f.write(fc)
```

This writes to `~/WickermanSupport/plugins/<plugin-id>/<file-path>`.

---

## 2. Core Embedded Constants (wickerman_support.py)

These are imported by `wickermaninstall.py` and written via `write_file()` during install.

### 2.1 MAIN_PY

| Field | Value |
|-------|-------|
| **Variable** | `MAIN_PY` |
| **Source file** | `wickerman_support.py` (line 10) |
| **Target path** | `~/wickerman/core_app/main.py` |
| **Container** | `wm-core` (NiceGUI dashboard) |
| **Content lines** | ~1108 |
| **Language** | Python |
| **Description** | The entire Wickerman OS dashboard: plugin management, git version control, HUD, Codex, system tab. Contains 3 additional embedded markdown constants inline (MANUAL, AI_PLUGIN_GUIDE, SOURCE_HELP) as string literals within this Python file. |

### 2.2 CORE_DOCKERFILE

| Field | Value |
|-------|-------|
| **Variable** | `CORE_DOCKERFILE` |
| **Source file** | `wickerman_support.py` (line 1124) |
| **Target path** | `~/wickerman/core_app/Dockerfile` |
| **Container** | `wm-core` (build definition) |
| **Content lines** | ~7 |
| **Language** | Dockerfile |
| **Description** | Python 3.11-slim base, installs nicegui, docker, psutil, nvidia-ml-py, requests. Runs `core_app/main.py`. |

### 2.3 DOWNLOADER_APP_PY

| Field | Value |
|-------|-------|
| **Variable** | `DOWNLOADER_APP_PY` |
| **Source file** | `wickerman_support.py` (line 1141) |
| **Target path** | `~/wickerman/downloader/app.py` |
| **Container** | `wm-downloader` |
| **Content lines** | ~156 |
| **Language** | Python |
| **Description** | Flask app for downloading models from HuggingFace. Supports browsing, direct URL, batch download, resume. |

### 2.4 DOWNLOADER_INDEX_HTML

| Field | Value |
|-------|-------|
| **Variable** | `DOWNLOADER_INDEX_HTML` |
| **Source file** | `wickerman_support.py` (line 1303) |
| **Target path** | `~/wickerman/downloader/templates/index.html` |
| **Container** | `wm-downloader` |
| **Content lines** | ~77 |
| **Language** | HTML (with inline JS + CSS) |
| **Description** | Single-page frontend for HuggingFace browser, direct URL downloads, active download manager, and model library view. |

### 2.5 DOWNLOADER_REQUIREMENTS

| Field | Value |
|-------|-------|
| **Variable** | `DOWNLOADER_REQUIREMENTS` |
| **Source file** | `wickerman_support.py` (line 1386) |
| **Target path** | `~/wickerman/downloader/requirements.txt` |
| **Container** | `wm-downloader` |
| **Content lines** | ~3 |
| **Language** | pip requirements |
| **Description** | `flask==3.0.*, requests==2.32.*, gunicorn==22.*` |

### 2.6 DOWNLOADER_DOCKERFILE

| Field | Value |
|-------|-------|
| **Variable** | `DOWNLOADER_DOCKERFILE` |
| **Source file** | `wickerman_support.py` (line 1388) |
| **Target path** | `~/wickerman/downloader/Dockerfile` |
| **Container** | `wm-downloader` (build definition) |
| **Content lines** | ~7 |
| **Language** | Dockerfile |
| **Description** | Python 3.11-slim, installs from requirements.txt, runs gunicorn on port 5000. |

### 2.7 GENERATE_NGINX_PY

| Field | Value |
|-------|-------|
| **Variable** | `GENERATE_NGINX_PY` |
| **Source file** | `wickerman_support.py` (line 1402) |
| **Target path** | `~/wickerman/nginx/generate_nginx.py` |
| **Container** | Runs on host (or inside `wm-core` via subprocess) |
| **Content lines** | ~103 |
| **Language** | Python |
| **Description** | Scans plugin manifests and generates `nginx.conf` with virtual host blocks. Produces `~/wickerman/nginx/nginx.conf` at runtime. Written with `chmod=0o755`. |

---

## 3. Documentation Constants (embedded inside MAIN_PY)

These three constants are defined inside the `MAIN_PY` string. They are NOT separate files on disk -- they live as Python string variables within `core_app/main.py` at runtime. They are rendered in the Codex and Source tabs of the NiceGUI dashboard.

### 3.1 MANUAL

| Field | Value |
|-------|-------|
| **Variable** | `MANUAL` (inside `MAIN_PY`) |
| **Source file** | `wickerman_support.py` (line 45, within the MAIN_PY string) |
| **Target path** | Inline in `~/wickerman/core_app/main.py` (not a separate file) |
| **Container** | `wm-core` |
| **Content lines** | ~188 |
| **Language** | Markdown |
| **Description** | Full user manual: getting started, architecture, plugins, agents, RAG, remote providers, model downloads, file locations, API reference, troubleshooting, security. Rendered in the Codex tab. |

### 3.2 AI_PLUGIN_GUIDE

| Field | Value |
|-------|-------|
| **Variable** | `AI_PLUGIN_GUIDE` (inside `MAIN_PY`) |
| **Source file** | `wickerman_support.py` (line 235, within the MAIN_PY string) |
| **Target path** | Inline in `~/wickerman/core_app/main.py` (not a separate file) |
| **Container** | `wm-core` |
| **Content lines** | ~72 |
| **Language** | Markdown |
| **Description** | Plugin authoring guide: manifest format, registry pull vs local build, rules, Node API for Flow Editor integration. Rendered in Codex tab under an expansion panel. |

### 3.3 SOURCE_HELP

| Field | Value |
|-------|-------|
| **Variable** | `SOURCE_HELP` (inside `MAIN_PY`) |
| **Source file** | `wickerman_support.py` (line 309, within the MAIN_PY string) |
| **Target path** | Inline in `~/wickerman/core_app/main.py` (not a separate file) |
| **Container** | `wm-core` |
| **Content lines** | ~60 |
| **Language** | Markdown |
| **Description** | Explains version control (git) concepts to end users: commits, diffs, working changes, timelines, the two-repo structure. Rendered in Source tab as an expansion panel. |

---

## 4. Plugin Manifests (JSON)

These are Python dicts in `wickerman_plugins/*.py`. The installer serializes them with `json.dumps(manifest, indent=2)` and writes them to `~/WickermanSupport/plugins/<filename>`.

| Manifest File | Dict Variable | Source File | Container | Has Embedded Files |
|---------------|---------------|-------------|-----------|-------------------|
| `wm-llama.json` | `WM_LLAMA` | `wm_llama.py` | `wm-llama` | Yes (`WM_LLAMA_FILES`) |
| `wm-chat.json` | `WM_CHAT` | `wm_chat.py` | `wm-chat` | Yes (`WM_CHAT_FILES`) |
| `wm-flow.json` | `WM_FLOW` | `wm_flow.py` | `wm-flow` | No (pulls `flowiseai/flowise:latest`) |
| `wm-trainer.json` | `WM_TRAINER` | `wm_trainer.py` | `wm-trainer` | Yes (`WM_TRAINER_FILES`) |
| `wm-forge.json` | `WM_FORGE` | `wm_forge.py` | `wm-forge` | Yes (`WM_FORGE_FILES`) |

### How manifests are assembled

Each plugin file (e.g., `wm_chat.py`) defines:
1. A dict `WM_CHAT` with metadata (name, description, icon, ports, etc.)
2. A dict `WM_CHAT_FILES` mapping relative file paths to content strings
3. At the bottom: `WM_CHAT["files"] = WM_CHAT_FILES` merges the files into the manifest
4. A tuple `PLUGIN_HOST` for `/etc/hosts` entries

The `__init__.py` aggregates everything into `ALL_PLUGINS` (dict) and `PLUGIN_HOSTS` (list).

### How manifests are serialized

In `wickermaninstall.py` line 248-250:
```python
for fname, manifest in ALL_PLUGINS.items():
    support_path = SUPPORT_DIR / "plugins" / fname
    write_file(support_path, json.dumps(manifest, indent=2))
```

The entire manifest including the `"files"` dict is serialized to JSON. This means the embedded source code is stored as JSON string values inside the `.json` manifest file.

---

## 5. Plugin Embedded Files

These files are extracted from the manifest `"files"` dict at runtime by the dashboard when a user clicks INSTALL. They are written to `~/WickermanSupport/plugins/<plugin-id>/`.

### 5.1 wm-llama (Model Router)

| Dict Key | Language | Lines | Runtime Target Path |
|----------|----------|-------|-------------------|
| `data/Dockerfile` | Dockerfile | ~16 | `~/WickermanSupport/plugins/wm-llama/data/Dockerfile` |
| `data/entrypoint.sh` | Shell (bash) | ~73 | `~/WickermanSupport/plugins/wm-llama/data/entrypoint.sh` |
| `data/test_chat.html` | HTML (with inline JS + CSS) | ~149 | `~/WickermanSupport/plugins/wm-llama/data/test_chat.html` |
| `data/manager.py` | Python | ~941 | `~/WickermanSupport/plugins/wm-llama/data/manager.py` |

**Variable**: `WM_LLAMA_FILES` in `wickerman_plugins/wm_llama.py`
**Build context**: `data/` (so `docker build` runs from `~/WickermanSupport/plugins/wm-llama/data/`)
**GPU**: Yes
**Base image**: `nvidia/cuda:12.2.0-devel-ubuntu22.04`

`manager.py` is the largest embedded file (~941 lines). It implements:
- Multi-model slot management (load/unload llama.cpp instances)
- RAG with FAISS vector search + SQLite chunks
- Remote provider proxying (OpenAI, Anthropic, Google, custom)
- Context trimming with auto-archive
- System prompt injection
- Full HTTP API server
- Agent configuration persistence

### 5.2 wm-chat (Chat)

| Dict Key | Language | Lines | Runtime Target Path |
|----------|----------|-------|-------------------|
| `data/Dockerfile` | Dockerfile | ~9 | `~/WickermanSupport/plugins/wm-chat/data/Dockerfile` |
| `data/app.py` | Python | ~157 | `~/WickermanSupport/plugins/wm-chat/data/app.py` |
| `data/templates/index.html` | HTML (with inline JS + CSS) | ~97 | `~/WickermanSupport/plugins/wm-chat/data/templates/index.html` |

**Variable**: `WM_CHAT_FILES` in `wickerman_plugins/wm_chat.py`
**Note**: `app.py` and `templates/index.html` are assigned via subscript (`WM_CHAT_FILES["data/app.py"] = ...`) rather than inline in the initial dict literal. Only `data/Dockerfile` is in the initial dict.
**Build context**: `data/`
**GPU**: No
**Base image**: `python:3.11-slim`

### 5.3 wm-forge (Code Forge)

| Dict Key | Language | Lines | Runtime Target Path |
|----------|----------|-------|-------------------|
| `data/Dockerfile` | Dockerfile | ~12 | `~/WickermanSupport/plugins/wm-forge/data/Dockerfile` |
| `data/app.py` | Python | ~136 | `~/WickermanSupport/plugins/wm-forge/data/app.py` |
| `data/templates/index.html` | HTML (with inline JS + CSS) | ~70 | `~/WickermanSupport/plugins/wm-forge/data/templates/index.html` |

**Variable**: `WM_FORGE_FILES` in `wickerman_plugins/wm_forge.py`
**Build context**: `data/`
**GPU**: No
**Network**: `wm-forge-net` (isolated, with gateway connected)
**Base image**: `python:3.11-slim`

### 5.4 wm-trainer (Model Trainer)

| Dict Key | Language | Lines | Runtime Target Path |
|----------|----------|-------|-------------------|
| `data/Dockerfile` | Dockerfile | ~13 | `~/WickermanSupport/plugins/wm-trainer/data/Dockerfile` |
| `data/app.py` | Python | ~179 | `~/WickermanSupport/plugins/wm-trainer/data/app.py` |
| `data/templates/index.html` | HTML (with inline JS + CSS) | ~60 | `~/WickermanSupport/plugins/wm-trainer/data/templates/index.html` |

**Variable**: `WM_TRAINER_FILES` in `wickerman_plugins/wm_trainer.py`
**Build context**: `data/`
**GPU**: Yes
**Base image**: `nvidia/cuda:12.2.0-devel-ubuntu22.04`

### 5.5 wm-flow (Flow Editor)

No embedded files. Uses a pre-built Docker Hub image (`flowiseai/flowise:latest`).

---

## 6. Dynamically Generated Content

These are NOT from string constants. They are built in `main()` using f-strings with runtime values (paths, GPU detection, username).

### 6.1 docker-compose.yml

| Field | Value |
|-------|-------|
| **Target path** | `~/wickerman/docker-compose.yml` |
| **Generated at** | `wickermaninstall.py` line 254-298 |
| **Dynamic values** | `INSTALL_DIR`, `SUPPORT_DIR`, GPU reservation block (conditional on `nvidia-smi`) |
| **Services defined** | `core`, `downloader`, `gateway` |

### 6.2 start.sh

| Field | Value |
|-------|-------|
| **Target path** | `~/wickerman/start.sh` |
| **Generated at** | `wickermaninstall.py` line 312-331 |
| **Dynamic values** | `shell_user`, `INSTALL_DIR`, `SUPPORT_DIR` |
| **chmod** | `0o755` |

### 6.3 .gitignore (install)

| Field | Value |
|-------|-------|
| **Target path** | `~/wickerman/.gitignore` |
| **Generated at** | `wickermaninstall.py` line 349-353 |
| **Content** | `__pycache__/`, `*.pyc`, `*.log`, `.env` |

### 6.4 .gitignore (support)

| Field | Value |
|-------|-------|
| **Target path** | `~/WickermanSupport/.gitignore` |
| **Generated at** | `wickermaninstall.py` line 364-371 |
| **Content** | `models/`, `datasets/`, `loras/`, `*.gguf`, `*.bin`, `*.safetensors`, `__pycache__/`, `*.pyc` |

### 6.5 nginx.conf (generated at start time, not install time)

| Field | Value |
|-------|-------|
| **Target path** | `~/wickerman/nginx/nginx.conf` |
| **Generated by** | `generate_nginx.py` (runs during `start.sh` and on plugin install/remove) |
| **Not an embedded constant** | Built dynamically from plugin manifests |

---

## 7. /etc/hosts Entries

Written directly (not via `write_file`) when running as root. Source: `HOSTS_NEEDED` + `PLUGIN_HOSTS`.

| Hostname | Source |
|----------|--------|
| `wickerman.local` | `HOSTS_NEEDED` in `wickermaninstall.py` |
| `downloader.wickerman.local` | `HOSTS_NEEDED` in `wickermaninstall.py` |
| `llama.wickerman.local` | `PLUGIN_HOST` in `wm_llama.py` |
| `chat.wickerman.local` | `PLUGIN_HOST` in `wm_chat.py` |
| `flow.wickerman.local` | `PLUGIN_HOST` in `wm_flow.py` |
| `trainer.wickerman.local` | `PLUGIN_HOST` in `wm_trainer.py` |
| `forge.wickerman.local` | `PLUGIN_HOST` in `wm_forge.py` |

---

## 8. Complete File Inventory

### Written at install time (by wickermaninstall.py)

| # | Constant | Target (relative to ~/wickerman/) | Type | Lines |
|---|----------|-----------------------------------|------|-------|
| 1 | `MAIN_PY` | `core_app/main.py` | Python | ~1108 |
| 2 | `CORE_DOCKERFILE` | `core_app/Dockerfile` | Dockerfile | ~7 |
| 3 | `DOWNLOADER_APP_PY` | `downloader/app.py` | Python | ~156 |
| 4 | `DOWNLOADER_INDEX_HTML` | `downloader/templates/index.html` | HTML | ~77 |
| 5 | `DOWNLOADER_REQUIREMENTS` | `downloader/requirements.txt` | pip requirements | ~3 |
| 6 | `DOWNLOADER_DOCKERFILE` | `downloader/Dockerfile` | Dockerfile | ~7 |
| 7 | `GENERATE_NGINX_PY` | `nginx/generate_nginx.py` | Python | ~103 |
| 8 | (dynamic) | `docker-compose.yml` | YAML | ~45 |
| 9 | (dynamic) | `start.sh` | Shell | ~20 |
| 10 | (dynamic) | `.gitignore` | gitignore | ~4 |

### Written at install time (to ~/WickermanSupport/plugins/)

| # | Dict | Target Filename | Type |
|---|------|----------------|------|
| 11 | `WM_LLAMA` | `wm-llama.json` | JSON manifest (with embedded files) |
| 12 | `WM_CHAT` | `wm-chat.json` | JSON manifest (with embedded files) |
| 13 | `WM_FLOW` | `wm-flow.json` | JSON manifest (no embedded files) |
| 14 | `WM_TRAINER` | `wm-trainer.json` | JSON manifest (with embedded files) |
| 15 | `WM_FORGE` | `wm-forge.json` | JSON manifest (with embedded files) |

### Written at runtime (by dashboard _install_task, to ~/WickermanSupport/plugins/)

| # | Dict[Key] | Target (relative to ~/WickermanSupport/plugins/) | Type | Lines |
|---|-----------|--------------------------------------------------|------|-------|
| 16 | `WM_LLAMA_FILES["data/Dockerfile"]` | `wm-llama/data/Dockerfile` | Dockerfile | ~16 |
| 17 | `WM_LLAMA_FILES["data/entrypoint.sh"]` | `wm-llama/data/entrypoint.sh` | Shell | ~73 |
| 18 | `WM_LLAMA_FILES["data/test_chat.html"]` | `wm-llama/data/test_chat.html` | HTML | ~149 |
| 19 | `WM_LLAMA_FILES["data/manager.py"]` | `wm-llama/data/manager.py` | Python | ~941 |
| 20 | `WM_CHAT_FILES["data/Dockerfile"]` | `wm-chat/data/Dockerfile` | Dockerfile | ~9 |
| 21 | `WM_CHAT_FILES["data/app.py"]` | `wm-chat/data/app.py` | Python | ~157 |
| 22 | `WM_CHAT_FILES["data/templates/index.html"]` | `wm-chat/data/templates/index.html` | HTML | ~97 |
| 23 | `WM_FORGE_FILES["data/Dockerfile"]` | `wm-forge/data/Dockerfile` | Dockerfile | ~12 |
| 24 | `WM_FORGE_FILES["data/app.py"]` | `wm-forge/data/app.py` | Python | ~136 |
| 25 | `WM_FORGE_FILES["data/templates/index.html"]` | `wm-forge/data/templates/index.html` | HTML | ~70 |
| 26 | `WM_TRAINER_FILES["data/Dockerfile"]` | `wm-trainer/data/Dockerfile` | Dockerfile | ~13 |
| 27 | `WM_TRAINER_FILES["data/app.py"]` | `wm-trainer/data/app.py` | Python | ~179 |
| 28 | `WM_TRAINER_FILES["data/templates/index.html"]` | `wm-trainer/data/templates/index.html` | HTML | ~60 |

### Inline documentation (not separate files, embedded in MAIN_PY)

| # | Variable | Type | Lines | Rendered Where |
|---|----------|------|-------|---------------|
| 29 | `MANUAL` | Markdown | ~188 | Codex tab |
| 30 | `AI_PLUGIN_GUIDE` | Markdown | ~72 | Codex tab (expansion panel) |
| 31 | `SOURCE_HELP` | Markdown | ~60 | Source tab (expansion panel) |

---

## 9. Total Embedded Code Size

| Category | Files | Total Lines |
|----------|-------|-------------|
| Core constants (wickerman_support.py) | 7 | ~1,461 |
| Documentation constants (inside MAIN_PY) | 3 | ~320 |
| wm-llama embedded files | 4 | ~1,179 |
| wm-chat embedded files | 3 | ~263 |
| wm-forge embedded files | 3 | ~218 |
| wm-trainer embedded files | 3 | ~252 |
| **TOTAL embedded source** | **23** | **~3,693** |

---

## 10. Extraction Notes

### Key considerations for extraction

1. **MAIN_PY is the largest single extraction** (~1108 lines). It contains three further inline markdown constants (MANUAL, AI_PLUGIN_GUIDE, SOURCE_HELP) that should be extracted to separate `.md` files and loaded at runtime via `Path("...").read_text()`.

2. **manager.py (wm-llama)** is the second largest (~941 lines). It is a complete HTTP server with RAG, multi-model orchestration, and provider proxying.

3. **Plugin files currently travel through JSON serialization.** The `"files"` dict is embedded in the JSON manifest. After extraction, the installer/dashboard should read files from disk instead of from the JSON.

4. **The `write_file()` calls in `wickermaninstall.py` lines 237-243** are the primary extraction targets for core files. After extraction, these should read from real files on disk rather than importing string constants.

5. **`docker-compose.yml` and `start.sh` are dynamically generated** with runtime values (paths, GPU detection, username). These cannot be simple file copies -- they need template rendering or the current f-string approach.

6. **`generate_nginx.py` produces `nginx.conf` at start time**, not at install time. The generator itself is a constant, but its output is dynamic.

7. **String escaping**: Constants use `r'''...'''` (raw triple-quoted strings). Some use `"""\` (no-newline-at-start). The Chat plugin's `app.py` uses single-quoted strings with `\n` for newlines rather than actual newlines. This will need careful handling during extraction.

8. **The CRT_CSS constant** (line ~41 in MAIN_PY) is a small CSS string (~2 lines) embedded inline. It could be extracted to a separate `.css` file.

9. **THEMES dict** (line ~32 in MAIN_PY) is a configuration dict, not a file to extract, but could be moved to a separate config file.
