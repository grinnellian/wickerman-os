# Contributing to Wickerman OS

## Development Setup

The easiest way to get a working dev environment is the dev container — it has Python, all dev tools, and Claude Code pre-installed.

### Option A: VS Code Dev Container (recommended)

1. Install [VS Code](https://code.visualstudio.com/) and the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
2. Open this repo in VS Code
3. Click "Reopen in Container" when prompted
4. You're done — terminal has `python`, `pytest`, `ruff`, `mypy`, `claude`, and `make`

### Option B: Standalone Docker (any terminal)

```bash
# Set GH_TOKEN so the container can git push
export GH_TOKEN=ghp_your_token_here  # or add to ~/.bashrc

docker compose -f docker-compose.dev.yml build
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml exec dev zsh
# Inside: make test, make lint, gh, claude, etc.
```

### Option C: Local (if you have Python 3.10+ and pip)

```bash
git clone https://github.com/grinnellian/wickerman-os.git
cd wickerman-os
pip install -e ".[dev]"
make test
```

## Dev Commands

```bash
make dev        # Install dev dependencies (option C only)
make test       # Run pytest (149 tests)
make lint       # Run ruff linter
make format     # Auto-format with ruff
make typecheck  # Run mypy
make ci         # lint + test (what GitHub Actions runs)
```

## Project Structure

```
wickerman-os/
├── wickermaninstall.py          # Single-file installer
├── wickerman_support.py         # Loads source from src/ for the installer
├── wickerman_plugins/           # Plugin manifest definitions
│   ├── __init__.py              # Plugin registry
│   ├── wm_llama.py              # Model Router manifest
│   ├── wm_chat.py               # Chat UI manifest
│   ├── wm_forge.py              # Code Forge manifest
│   ├── wm_trainer.py            # Model Trainer manifest
│   └── wm_flow.py               # Flow Editor manifest (wraps Flowise)
├── src/                         # Extracted runtime source code
│   ├── core/                    # wm-core dashboard (NiceGUI)
│   ├── downloader/              # wm-downloader (Flask, HuggingFace)
│   ├── nginx/                   # Nginx config generator
│   ├── plugins/                 # Plugin container source
│   │   ├── llama/               # Model Router (HTTP server + RAG)
│   │   ├── chat/                # Chat UI (Flask)
│   │   ├── forge/               # Code Forge (Flask + subprocess)
│   │   └── trainer/             # Model Trainer (Flask + Unsloth)
│   └── shared/                  # Shared utilities (safe_path, version)
├── tests/                       # pytest test suite
├── .devcontainer/               # Dev container config (Dockerfile, firewall)
├── .github/workflows/           # CI pipeline (ruff + pytest)
├── models/                      # Place .gguf model files here
├── CHANGELOG.md                 # What changed and why
├── REVIEW.md                    # Independent code review
├── BETA2_PLAN.md                # Standardization plan and issue tracker
└── EXTRACTION_MAP.md            # How embedded source maps to files
```

## How the Code Flows

The source code lives in `src/`. At install time:

1. `wickerman_support.py` reads source files via `Path.read_text()`
2. Plugin manifests in `wickerman_plugins/` load their files the same way
3. `wickermaninstall.py` imports these modules and writes the source to `~/wickerman/`
4. Plugin source is embedded in JSON manifests and extracted at container install time by the dashboard

## Testing

Tests are in `tests/` and use pytest. They test reimplemented pure functions rather than importing the full apps (which need Flask, NiceGUI, etc.):

- `test_plugin_schema.py` — validates all 5 plugin manifests have correct structure
- `test_core_utilities.py` — tests `safe_path`, `_conv_path`, `parse_hf_input`, `_build_cmd`, `_resolve_model`, `resolve_volume`
- `test_extraction_fidelity.py` — verifies extracted source files load correctly and embedded Python parses
- `test_agent_pipeline.py` — tests the agent pipeline (system prompt injection, settings merging, RAG chunking)

Run with: `make test` or `python -m pytest tests/ -v`

## Security

If you find a security vulnerability, please report it responsibly. Key areas to watch:

- **Path traversal:** All user-supplied paths must go through `safe_path()` — see `src/shared/security.py`
- **Volume mounts:** `resolve_volume()` validates paths within allowed directories
- **CORS:** Configured via `CORS_ORIGINS` environment variable (default: localhost only)
- **Network:** Nginx binds to `127.0.0.1` by default — LAN access is opt-in
- **Dev container firewall:** Outbound HTTP/HTTPS is routed through a tinyproxy forward proxy that filters by domain name. iptables blocks direct outbound from all users except the proxy. See `.devcontainer/allowlist.conf` for the domain list and `.devcontainer/init-firewall.sh` for the setup. To add a domain at runtime: edit `/etc/tinyproxy/allowlist` and `sudo kill -HUP $(pidof tinyproxy)`.
- **GH_TOKEN:** Forwarded into the container for git push — use a fine-grained PAT scoped to this repo with Contents read/write only

## Code Style

- Python 3.10+ syntax
- Linted with ruff (config in `pyproject.toml`)
- Original author's code in `src/` is excluded from linting — style changes proposed separately
- Type hints on public interfaces (ongoing)
- No bare `except:` — always use `except Exception:`
