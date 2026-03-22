# Wickerman OS — Independent Code Review

> Thorough, neutral third-party review — code and documentation examination only, no installation or testing.
> Date: 2026-03-21 | Reviewer: Claude Opus 4.6 | Codebase: wickerman-os @ 84e5170 (v5.2.0)

---

## Executive Summary

Wickerman OS is a **self-hosted AI workstation** packaged as a Docker-based platform. It provides local LLM inference (via llama.cpp), a chat UI, visual pipeline editor, code generation sandbox, and LoRA fine-tuning — all behind a NiceGUI dashboard and nginx reverse proxy.

The codebase is **~3,860 lines of Python** across 8 source files plus a 27-line shell script, totaling 248KB. The entire system — including full application source code for five microservices, three Dockerfiles, HTML/JS frontends, and user documentation — is distributed as two Python files and a plugin package, using an unusual "code as string constants" pattern.

**Overall assessment**: A well-conceived personal AI toolkit at **beta maturity**. The architecture is sound for single-user local deployment. The code is pragmatic and functional, showing real iteration on operational concerns (upgrade stashing, download resumption, atomic writes, hardware detection). However, it has meaningful security gaps for any networked deployment, no automated tests, and the embedded-source-code pattern creates significant maintainability constraints. The "v5.2.0" label on a single-commit repository overstates observable maturity.

### Scores

| Dimension | Rating | Notes |
|-----------|--------|-------|
| **Concept & Design** | Strong | Coherent vision, good component decomposition, practical feature set |
| **Code Quality** | Adequate | Functional and pragmatic; some anti-patterns; no type hints or tests |
| **Documentation** | Good | Polished README, inline help text, built-in manual; lacks changelog |
| **Security** | Weak | No auth, open CORS, path traversals, Docker socket exposure |
| **Maintainability** | Below average | Code-as-strings pattern defeats static analysis and IDE tooling |
| **Production Readiness** | Prototype/Beta | Suitable for personal use; not for shared or networked deployment |

---

## Table of Contents

1. [What the Project Is](#what-the-project-is)
2. [Repository Structure](#repository-structure)
3. [Architecture Analysis](#architecture-analysis)
4. [Core Infrastructure Review](#core-infrastructure-review)
5. [Plugin System Review](#plugin-system-review)
6. [Security Assessment](#security-assessment)
7. [Code Quality Assessment](#code-quality-assessment)
8. [Documentation Assessment](#documentation-assessment)
9. [Maturity & Project Health](#maturity--project-health)
10. [Recommendations](#recommendations)
11. [Detailed Sub-Reviews](#detailed-sub-reviews)

---

## What the Project Is

Wickerman OS is a Docker Compose application that deploys:

- **wm-core**: A NiceGUI web dashboard for managing containers, viewing system stats (CPU/RAM/GPU/VRAM), plugin lifecycle management, git-based version control UI, and a searchable documentation viewer (Codex)
- **wm-llama**: The Model Router — multi-model inference server wrapping llama.cpp, with OpenAI-compatible API, remote provider support (OpenAI/Anthropic/Gemini), per-agent RAG memory (FAISS + SQLite), and an agent pipeline (system prompt → trim → archive → RAG → proxy)
- **wm-chat**: Multi-conversation chat UI proxying to wm-llama
- **wm-forge**: AI-assisted code generation with Python/Node/Bash execution sandbox
- **wm-trainer**: LoRA fine-tuning via Unsloth
- **wm-flow**: Visual AI pipeline editor (wraps Flowise)
- **wm-gateway**: Nginx reverse proxy unifying all services under `wickerman.local`
- **wm-downloader**: HuggingFace model browser and downloader with resume support

Despite the "OS" branding, this is an application suite, not an operating system. The name is marketing language.

---

## Repository Structure

```
wickerman-os/                    (this repo — the "source of truth")
├── wickermaninstall.py          394 lines — single-file installer
├── wickerman_support.py        1506 lines — all application source as string constants
├── wickerman_plugins/
│   ├── __init__.py               39 lines — plugin registry
│   ├── wm_llama.py             1219 lines — model router plugin
│   ├── wm_chat.py               222 lines — chat UI plugin
│   ├── wm_forge.py              253 lines — code forge plugin
│   ├── wm_trainer.py            293 lines — model trainer plugin
│   └── wm_flow.py                38 lines — flow editor plugin
├── models/                      empty (placeholder for .gguf files)
├── stop.sh                       27 lines — container shutdown
├── README.md                    project documentation
├── LICENSE                      MIT (Tabulanis, 2025-2026)
└── .gitignore
```

At install time, the installer writes all embedded source code to `~/wickerman/` and persistent data to `~/WickermanSupport/`, then runs `docker compose up`.

---

## Architecture Analysis

### Design Decisions

**Strength — Component Decomposition**: Each concern gets its own container with a clear boundary. The Model Router is the central abstraction — all LLM access goes through its unified API. This is a good architectural choice that enables agent configuration, RAG, and provider routing in one place.

**Strength — Plugin System**: The manifest-based plugin design is extensible. Wrapping Flowise (wm-flow) demonstrates that third-party images integrate cleanly. The node API pattern across plugins enables composable pipelines.

**Strength — Operational Maturity**: The installer handles upgrade-safe stashing of user data, cross-device moves, sudo user detection, and GPU auto-detection. The downloader supports HTTP Range resume. The entrypoint script handles CPU feature detection for llama.cpp optimization. These details suggest real-world iteration.

**Weakness — Code as String Constants**: The defining architectural decision is embedding all application source code as Python string literals in `wickerman_support.py` and the plugin files. This means:

- **No static analysis**: Linters, type checkers, formatters cannot process the actual runtime code
- **No IDE support**: No autocomplete, go-to-definition, or refactoring for ~2,500 lines of runtime Python
- **No unit testing**: Code can't be tested without first extracting to files
- **Line number mismatch**: Runtime errors reference line numbers that don't match the source file
- **Merge pain**: Version control diffs of embedded code are difficult to review

The trade-off is distribution simplicity — two files to clone, one command to install. Whether this trade-off is worthwhile depends on the project's priorities.

**Weakness — Monolithic Functions**: The dashboard's `index()` function is ~480 lines of nested closures. The Model Router's `do_GET`/`do_POST` handlers use long `elif` chains. These work but are difficult to navigate, test, or extend.

### Dependency Map

```
wickermaninstall.py
  ├── imports: wickerman_support.py (required — exits on failure)
  ├── imports: wickerman_plugins/ (optional — falls back to empty)
  └── writes: ~/wickerman/ (docker-compose.yml, start.sh, app source files)

Runtime (Docker Compose):
  wm-core (NiceGUI) ──────► Docker socket (root-equivalent host access)
  wm-gateway (nginx) ──────► reverse proxies all wm-* containers
  wm-chat ─────────────────► wm-llama (LLM inference)
  wm-forge ────────────────► wm-llama (code generation)
  wm-trainer ──────────────► shared volumes (models, datasets, loras)
  wm-flow ─────────────────► wm-llama + node APIs on chat/forge/trainer
  wm-downloader ───────────► HuggingFace API (external)
```

### External Dependencies

| Layer | Dependencies |
|-------|-------------|
| Host | Docker, Docker Compose, Python 3, git, nvidia-smi (optional) |
| Core container | nicegui, docker SDK, psutil, nvidia-ml-py, requests |
| Llama container | llama.cpp (built from source), pynvml, requests, tiktoken, faiss-cpu, numpy |
| Chat/Forge containers | Flask 3.0.x, requests 2.32.x, gunicorn 22.x |
| Trainer container | PyTorch, Unsloth, Transformers, TRL, PEFT, CUDA 12.2 |
| External services | HuggingFace API (model browsing/downloading) |

---

## Core Infrastructure Review

### wickermaninstall.py (394 lines)

A procedural single-file installer that:
1. Parses CLI args (`--reset`, `--hard-reset`)
2. Detects sudo context and resolves real user's home
3. Performs upgrade-safe stashing of user directories
4. Creates persistent storage in `~/WickermanSupport/`
5. Copies model files from repo `models/` directory
6. Writes all application source from string constants to disk
7. Generates `docker-compose.yml` with conditional GPU passthrough
8. Generates `start.sh`
9. Patches `/etc/hosts` (when root)
10. Initializes git repos

**Notable concerns**:
- `run()` helper uses `shell=True` with f-string path interpolation — safe given controlled inputs, but sets a risky precedent
- `sudo rm -rf` used on paths derived from constants — correct but inherently dangerous pattern
- No rollback mechanism if installation fails partway through
- No Docker presence/version check before attempting operations
- Git init blocks for two repos are nearly identical (DRY violation)

### wickerman_support.py (1,506 lines)

Acts as a data store containing the full source code of the dashboard application (~1,108 lines), downloader application (~155 lines), nginx generator (~105 lines), and all documentation as string constants.

**Dashboard (MAIN_PY)**: A NiceGUI SPA with system monitoring, Docker container lifecycle management, git version control UI, searchable documentation viewer, and five visual themes. The Docker SDK is used for container operations. The `index()` function is a monolith (~480 lines).

**Downloader (DOWNLOADER_APP_PY)**: Flask app for browsing HuggingFace model repos and downloading GGUF files with HTTP Range resume support. Persists download state for crash recovery.

**Nginx Generator (GENERATE_NGINX_PY)**: Reads plugin JSON manifests and builds nginx server blocks with dynamic upstream resolution.

**Notable concerns**:
- `storage_secret="wm-secret"` — hardcoded, predictable NiceGUI session signing secret
- `chmod 0o777` on volume mount directories — overly permissive
- Volume path traversal: `resolve_volume()` does simple string replacement without validating paths stay within intended directories; a malicious plugin manifest could mount arbitrary host paths
- Downloader accepts arbitrary URLs via `/api/download` (no domain validation)
- Nginx gateway binds to `0.0.0.0:80` — exposes system to network
- Unused import: `from collections import deque`
- Nginx strips `X-Frame-Options` and `Content-Security-Policy` headers to allow iframe embedding of plugin UIs

### stop.sh (27 lines)

Straightforward shutdown: runs `docker compose down`, then stops any remaining `wm-*` containers. Minor issue: stops but doesn't remove plugin containers, causing accumulation of stopped containers over repeated cycles.

---

## Plugin System Review

Detailed findings are in [`wickerman_plugins/REVIEW.md`](wickerman_plugins/REVIEW.md). Key highlights:

### wm_llama (Model Router) — The Core Engine

The most sophisticated component. Multi-model management, remote provider routing, RAG with FAISS+SQLite, agent pipeline, unified OpenAI-compatible API. Well-designed slot-based architecture with thread safety and process cleanup. Main concerns: path traversal in static serving, `CORS *`, mutable global `EMBED_DIM` causing silent RAG corruption, no streaming support.

### wm_chat (Chat UI)

Clean proxy pattern with atomic file writes and path traversal protection. Main concerns: bare except clauses hiding errors, no streaming (user waits for full response), no file locking for concurrent access.

### wm_forge (Code Forge)

Good path traversal protection via `safe_path()`, runs as non-root. By design, executes arbitrary user code — the main risk is network exposure without authentication. XSS vulnerability in file listing, `export_project()` ignores its `files` parameter.

### wm_trainer (Model Trainer)

LoRA fine-tuning via Unsloth. **Path traversal vulnerability**: `output_name` parameter used directly in file paths without `safe_path()` validation. Runs as root in container. Hardcoded `fp16=True` may fail on some GPUs. Claims Alpaca dataset support but doesn't implement it.

### wm_flow (Flow Editor)

Configuration-only wrapper around Flowise. Hardcoded default credentials (`wickerman/wickerman`). Uses unpinned `:latest` image tag.

---

## Security Assessment

### Threat Model

Wickerman OS is designed as a **local-only, single-user tool**. The security posture reflects this — there is no authentication, authorization, or encryption anywhere. This is acceptable if the system is truly isolated, but the architecture creates several risks:

### Critical Findings

| # | Finding | Location | Impact |
|---|---------|----------|--------|
| 1 | **No authentication on any service** | All plugins + dashboard | Any network-reachable client has full control: container management, code execution, model manipulation, conversation access |
| 2 | **Docker socket mounted in core container** | `wickerman_support.py` compose generation | Root-equivalent host access — any code running in the dashboard can control the host via Docker |
| 3 | **Path traversal in wm_trainer** | `wm_trainer.py` `output_name` param | Can write files outside intended directory |
| 4 | **Path traversal in wm_llama** | `wm_llama.py` static file serving | `lstrip('/')` insufficient; `os.path.join` resolves `..` |
| 5 | **Volume path traversal** | `wickerman_support.py` `resolve_volume()` | Malicious plugin manifests can mount arbitrary host paths |
| 6 | **CORS `*` on Model Router** | `wm_llama.py` | Any website can call all LLM APIs from user's browser |
| 7 | **Arbitrary code execution without auth** | `wm_forge.py` `/api/run` | By design, but no network boundary enforcement |
| 8 | **Hardcoded session secret** | `wickerman_support.py` `storage_secret="wm-secret"` | Session cookies can be forged by anyone who reads the source |
| 9 | **`chmod 0o777` on volumes** | `wickerman_support.py` | World-writable volume mount directories |
| 10 | **Nginx binds `0.0.0.0:80`** | compose generation | Entire system exposed to network by default |

### Mitigating Context

The system is explicitly designed for local use, and the README does not encourage network exposure. Docker isolation provides a meaningful boundary for most attack scenarios. The primary real-world risk is LAN exposure — if the host has a non-localhost IP, everything is accessible to other devices on the network.

---

## Code Quality Assessment

### Strengths

- **Pragmatic problem-solving**: The code consistently chooses practical solutions — atomic writes, HTTP Range resume, upgrade stashing, hardware detection, graceful degradation
- **Consistent patterns**: All plugins follow the same manifest structure, the same node API convention, the same Flask/gunicorn stack
- **Solid operations code**: The installer's sudo detection, cross-device move handling, and GPU passthrough logic show real-world polish
- **Good path validation** where it exists (`safe_path()` in forge/trainer, `isalnum()` in chat)

### Weaknesses

- **No type hints**: Zero annotations across ~3,860 lines. This is consistent but limits tooling and contributor onboarding
- **No automated tests**: Zero test files anywhere. No CI/CD. Bugs are discoverable only at runtime
- **Bare `except:` clauses**: Multiple instances swallowing `KeyboardInterrupt` and `SystemExit`
- **Monolithic functions**: Dashboard `index()` (~480 lines), Model Router `do_GET`/`do_POST` (long elif chains)
- **`shell=True` with f-strings**: In the installer's `run()` helper — works safely in context but is a latent injection risk
- **DRY violations**: Git init blocks duplicated in installer; chat logic duplicated in wm_chat; `safe_path()` duplicated across plugins
- **Compressed code style**: Multi-statement lines, single-line try/except, short variable names in UI code

### Metrics

| Metric | Value |
|--------|-------|
| Total Python LOC | ~3,860 |
| Test files | 0 |
| Type-annotated functions | 0 |
| TODO/FIXME markers | 1 (`/* future */` stub in forge) |
| Bare `except:` clauses | ~8 |
| Dead imports | 1 (`deque` in support) |

---

## Documentation Assessment

### Strengths

- **README.md**: Well-structured, clear quick-start path, honest about requirements, good project structure diagram, practical API examples, proper credits
- **Built-in manual**: ~230 lines of Markdown served through the Codex UI tab
- **Plugin authoring guide**: ~65 lines explaining manifest schema and conventions
- **Per-plugin help text**: Operational documentation embedded in each plugin manifest
- **models/README.md**: Appropriate minimal placeholder

### Weaknesses

- **No changelog**: Version 5.2.0 but no record of what changed across versions
- **No contributing guide**: No guidance for external contributors
- **No troubleshooting section**: Common failure modes not documented
- **No security documentation**: No guidance on network exposure, no threat model, no API key handling best practices
- **Version drift**: `__init__.py` and `wm_flow.py` say v5.1.0; rest says v5.2.0
- **Missing Codex tab docs**: "Codex" mentioned in First Steps but not documented in README

---

## Maturity & Project Health

### Version History

The entire repository consists of **one commit** (84e5170, dated 2026-03-21). The version badge claims **v5.2.0**. There are no tags, no branches beyond `main`, no prior commits, and no changelog.

This strongly suggests the project has a private development history that was squashed before publication. The codebase volume (~3,860 lines), operational polish (upgrade stashing, hardware detection, resume downloads), and multi-component architecture are consistent with genuine iteration — this is not a weekend project. However, the squashed history makes it impossible to assess:

- Development velocity or cadence
- Bug-fix patterns
- Code review practices
- How the code evolved to its current state
- Whether prior versions actually existed (supporting the 5.x version claim)

### Signs of Maturity

- Upgrade-safe installation (stash and restore user data)
- HTTP Range resume in downloader
- Atomic file writes in multiple locations
- Hardware auto-detection (CPU features, CUDA)
- Graceful degradation (GPU optional, plugins optional)
- Process cleanup via atexit and signal handlers

### Signs of Immaturity

- Zero automated tests
- Zero type annotations
- No CI/CD pipeline
- No release process (no tags, no changelog)
- Several security shortcuts (no auth, hardcoded secrets, `chmod 777`)
- Monolithic functions that resist refactoring
- Code-as-strings defeats standard development tooling

---

## Recommendations

These are ordered by estimated impact-to-effort ratio:

### High Priority

1. **Fix path traversal in wm_trainer**: Apply `safe_path()` to the `output_name` parameter. One-line fix, closes a real vulnerability.

2. **Fix path traversal in wm_llama static serving**: Validate that resolved paths start with `PUBLIC_DIR` before serving.

3. **Bind nginx to `127.0.0.1`**: Change the compose generation to bind port 80 to localhost only (`127.0.0.1:80:80`). Users who want LAN access can change this consciously.

4. **Generate a random `storage_secret`**: Create at install time, persist to a file, load at runtime. Trivial change, eliminates session forgery.

5. **Fix `EMBED_DIM` mutation**: Store the embedding dimension per FAISS index (e.g., in SQLite metadata) rather than using a mutable global. Prevents silent RAG corruption when models change.

### Medium Priority

6. **Add basic auth to nginx**: Even HTTP Basic Auth with a user-chosen password would significantly improve the security posture.

7. **Replace bare `except:` with `except Exception:`**: Preserves KeyboardInterrupt/SystemExit handling. Simple find-and-replace.

8. **Add streaming support to wm_llama and wm_chat**: Currently hardcoded `stream: False`. For an LLM chat interface, streaming is a significant UX improvement.

9. **Pin Flowise image version**: Replace `:latest` with a specific version tag for reproducible builds.

10. **Add `safe_path()` to `output_name` in wm_trainer**: Reuse the existing pattern from model/dataset path validation.

### Lower Priority (Quality of Life)

11. **Extract embedded source to real files**: Move from code-as-strings to a proper file tree, with the installer copying/symlinking files. Enables IDE support, linting, and testing.

12. **Add type hints**: Even just function signatures would improve tooling and documentation.

13. **Add a basic test suite**: At minimum, test the plugin manifest schema, `safe_path()`, and the agent pipeline logic.

14. **Create a changelog**: Even a `CHANGELOG.md` with a single entry for v5.2.0 would establish the practice.

15. **Break up monolithic functions**: Extract the dashboard `index()` into component functions; add a simple routing table to the Model Router.

---

## Detailed Sub-Reviews

- [Plugin System Review](wickerman_plugins/REVIEW.md) — detailed analysis of all five plugins
- [Models Directory Review](models/REVIEW.md) — placeholder directory assessment

---

*This review was conducted by examining source code and documentation only. No code was executed, installed, or tested. Findings are based on static analysis and architectural reasoning.*
