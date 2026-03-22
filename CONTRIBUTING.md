# Contributing to Wickerman OS

## Development Setup

```bash
# Clone the repo
git clone https://github.com/grinnellian/wickerman-os.git
cd wickerman-os

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
make test

# Run linter
make lint

# Format code
make format
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
│   └── shared/                  # Shared utilities
├── tests/                       # pytest test suite
├── models/                      # Place .gguf model files here
└── docs/                        # Review and planning documents
```

## How the Code Flows

The source code lives in `src/`. At install time:

1. `wickerman_support.py` reads source files via `Path.read_text()`
2. Plugin manifests in `wickerman_plugins/` load their files the same way
3. `wickermaninstall.py` imports these modules and writes the source to `~/wickerman/`
4. Plugin source is embedded in JSON manifests and extracted at container install time by the dashboard

## Testing

Tests are in `tests/` and use pytest:

- `test_plugin_schema.py` — validates plugin manifest structure
- `test_core_utilities.py` — tests pure utility functions (reimplemented for isolation)
- `test_extraction_fidelity.py` — verifies extracted source files load correctly

Run with: `make test` or `python -m pytest tests/ -v`

## Security

If you find a security vulnerability, please report it responsibly. Key areas to watch:

- Path traversal: all user-supplied paths must go through `safe_path()`
- Volume mounts: `resolve_volume()` validates paths within allowed directories
- CORS: configured via `CORS_ORIGINS` environment variable
- Network: nginx binds to `127.0.0.1` by default

## Code Style

- Python 3.10+ syntax
- Linted with ruff (config in `pyproject.toml`)
- Type hints on public interfaces (ongoing)
- No bare `except:` — always use `except Exception:`
