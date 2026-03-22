# Changelog

All notable changes to Wickerman OS will be documented in this file.

## [Unreleased] — Beta 2 Standardization

### Added
- `pyproject.toml` with project metadata, dev dependencies, tool config
- `Makefile` for dev commands (test, lint, format, typecheck, ci)
- `.editorconfig` for consistent whitespace
- `.github/workflows/ci.yml` — lint + test on push/PR
- `EXTRACTION_MAP.md` documenting the full embedded source pipeline
- `REVIEW.md` — independent code review at top level and per-directory
- `BETA2_PLAN.md` — phased standardization plan with GitHub issue tracking
- `src/` directory with all runtime source extracted to real files
- `src/shared/security.py` — canonical `safe_path()` implementation
- `src/shared/version.py` — single source of truth for version string
- `tests/test_plugin_schema.py` — plugin manifest schema validation
- `tests/test_core_utilities.py` — unit tests for safe_path, _conv_path, parse_hf_input, _build_cmd, _resolve_model, resolve_volume
- `tests/test_extraction_fidelity.py` — verifies extracted files match constants

### Changed
- `wickerman_support.py` and plugin files now use `Path.read_text()` instead of inline string constants
- Nginx gateway binds to `127.0.0.1:80` instead of `0.0.0.0:80`
- Storage secret generated randomly on first run (was hardcoded `wm-secret`)
- CORS `Access-Control-Allow-Origin` is now configurable via `CORS_ORIGINS` env var (was `*`)
- All bare `except:` replaced with `except Exception:` (8 instances)
- Flowise image pinned to `2.2.7` (was `:latest`)
- `stop.sh` now removes stopped plugin containers (was only stopping them)
- `export_project()` in forge now zips only specified files (was ignoring the parameter)
- `list_models()` in trainer now supports directory-based HuggingFace models
- Duplicate git-init blocks in installer extracted to `init_git_repo()` helper
- Version strings unified to v5.2.0 across all files

### Fixed
- **Security**: Path traversal in wm_trainer via `output_name` parameter
- **Security**: Path traversal in wm_llama static file serving
- **Security**: Path traversal in `resolve_volume()` — validates paths within allowed directories
- **Security**: EMBED_DIM mutation causing silent RAG corruption when embedding model changes
- Removed unused `from collections import deque` import

## [5.2.0] — 2026-03-21

Initial public release. Agent orchestration, RAG, remote providers.
