# Plugin System Code Review

> Independent third-party review — code and documentation examination only, no installation or testing.
> Date: 2026-03-21 | Reviewer: Claude Opus 4.6 | Codebase: wickerman-os @ 84e5170

---

## Plugin Architecture Overview

The plugin system uses a **flat registry** pattern. Each plugin is a Python module exporting:
- A manifest dictionary (`WM_*`) with container metadata (name, ports, volumes, env, nginx host, help text)
- A `PLUGIN_HOST` tuple for `/etc/hosts` entries
- Optionally, a `WM_*_FILES` dictionary mapping file paths to embedded source code as Python string literals

`__init__.py` manually imports all five plugins and re-exports `ALL_PLUGINS` (dict of JSON filenames to manifests) and `PLUGIN_HOSTS` (list of host tuples). There is no base class, protocol, abstract interface, or schema validation. Adding a plugin requires editing `__init__.py` by hand.

**Plugins in the system:**

| Plugin | Type | Purpose | Complexity |
|--------|------|---------|------------|
| wm_llama | Build from source | Model router, RAG, multi-model management | ~940 lines embedded Python |
| wm_chat | Build from source | Multi-conversation chat UI | ~140 lines embedded Python |
| wm_forge | Build from source | AI-assisted code generation + execution sandbox | ~115 lines embedded Python |
| wm_trainer | Build from source | LoRA fine-tuning via Unsloth | ~130 lines embedded Python |
| wm_flow | Pre-built image | Visual pipeline editor (wraps Flowise) | Configuration only |

---

## wm_llama.py — Model Router (1,219 lines)

The most complex and architecturally significant component. Acts as the central AI inference layer.

### What It Does

- **Multi-model management**: Load/unload multiple GGUF models simultaneously via llama.cpp's `llama-server`, each on its own port
- **Remote providers**: Route to OpenAI, Anthropic, Google Gemini, or custom OpenAI-compatible endpoints
- **RAG**: Per-agent FAISS vector search + SQLite chunk storage, with automatic archival of trimmed context
- **Agent pipeline**: System prompt injection → context trimming → auto-archive → RAG retrieval → inject context → proxy to backend
- **Unified API**: OpenAI-compatible `POST /v1/chat/completions`
- **VRAM monitoring**: Real-time GPU memory tracking via pynvml

### Strengths

- Well-designed slot-based architecture with alias resolution and fuzzy model matching
- Thread-safe slot mutations via `_slots_lock`
- Atomic FAISS index writes (write to `.tmp`, then `os.replace()`)
- API keys saved with `0o600` permissions in a separate file
- Process cleanup via `atexit` and signal handlers (SIGTERM/SIGINT)
- Entrypoint shell script handles hardware detection (AVX/AVX2/SSE3, CUDA) and build caching

### Issues Found

| Issue | Severity | Detail |
|-------|----------|--------|
| Path traversal in static file serving | Medium | `self.path.lstrip('/')` is insufficient; `os.path.join` can still resolve `..` sequences to paths outside `PUBLIC_DIR` |
| CORS `Access-Control-Allow-Origin: *` | Medium | Any website in the user's browser can call all API endpoints |
| Mutable global `EMBED_DIM` | Medium | If embedding model changes, FAISS indices built with previous dimensions silently produce wrong results |
| Bare `except:` clauses (6 instances) | Low | Swallows `KeyboardInterrupt` and `SystemExit` on critical paths |
| "Slow start" fallback marks unready models ready | Low | After 150s, models that haven't crashed but aren't healthy are marked "ready" |
| No streaming support | Functional gap | `stream: False` is hardcoded; client `stream` parameter silently ignored |
| No authentication | Design choice | All endpoints fully open to network |
| Monolithic HTTP handler | Maintainability | `do_GET`/`do_POST` with long `elif` chains, no routing framework |

### Dependencies

Runtime: Python 3.11, pynvml, requests, tiktoken, faiss-cpu, numpy
External: llama.cpp server binary (built from source in container)

---

## wm_chat.py — Chat UI (222 lines)

### What It Does

- Multi-conversation management with server-side persistence (JSON files on disk)
- Proxies all LLM calls to wm-llama's `/v1/chat/completions`
- Full single-page chat UI with sidebar, agent selector, context meter
- Node API for wm-flow pipeline integration

### Strengths

- Atomic file writes via `os.replace()` for crash safety
- Conversation ID validation with `cid.isalnum()` prevents path traversal
- Clean proxy pattern — thin conversation layer over the Model Router
- XSS protection via `esc()` using `textContent`/`innerHTML` sanitization

### Issues Found

| Issue | Severity | Detail |
|-------|----------|--------|
| Bare `except: pass` in `list_conversations` | Low | Corrupted JSON files silently disappear from listings |
| `/api/agents` swallows all errors | Low | Connection failures, JSON decode errors invisible to caller |
| No server-side message length limit | Low | 16K char warning is client-side only; API accepts arbitrary sizes |
| Chat logic duplicated | Maintainability | `/api/chat` and `/node/execute` duplicate the LLM call pattern |
| No streaming | Functional gap | User sees nothing until full response completes |
| No file locking | Concurrency | Gunicorn 1 worker / 4 threads — concurrent writes to same conversation can race |
| No authentication | Design choice | Any network client can CRUD all conversations |

### Dependencies

Runtime: Flask 3.0.x, requests 2.32.x, gunicorn 22.x

---

## wm_forge.py — Code Forge (253 lines)

### What It Does

- LLM-assisted code generation from natural-language prompts
- Code execution sandbox supporting Python, Node.js, and Bash
- File save/list/export to shared workspace volume
- Node API for wm-flow pipeline integration

### Strengths

- `safe_path()` validates against path traversal via `os.path.abspath` comparison
- Subprocess execution uses `capture_output=True` and `timeout`
- Dockerfile runs as non-root user (`forgeuser`)
- Consistent JSON API with proper status codes

### Issues Found

| Issue | Severity | Detail |
|-------|----------|--------|
| Arbitrary code execution, no auth | High (by design) | `/api/run` executes user-supplied Python/Node/Bash; any network client can invoke |
| XSS in file listing | Medium | `loadFiles` renders filenames into `onclick` attribute without escaping |
| User-controllable timeout | Low | Caller can set `timeout=999999` to keep processes running indefinitely |
| `export_project()` ignores `files` param | Bug | Always zips entire workspace regardless of specified files |
| `loadFile()` is a stub | Incomplete | `/* future: load file content into editor */` — clicking files does nothing |
| `esc()` missing `"` and `'` | Low | HTML escaping incomplete for attribute contexts |

### Dependencies

Runtime: Flask 3.0.x, requests 2.32.x, gunicorn 22.x, Node.js

---

## wm_trainer.py — Model Trainer (293 lines)

### What It Does

- LoRA fine-tuning of language models using Unsloth library
- Web UI for model/dataset selection, hyperparameter configuration
- Background training with real-time log polling
- LoRA adapter output to shared volume

### Strengths

- `safe_path()` applied to model and dataset paths
- Thread lock prevents concurrent training runs (returns 409 Conflict)
- Training log capped at 500 entries to prevent memory growth
- Heavy library imports deferred to training time (avoids startup cost)

### Issues Found

| Issue | Severity | Detail |
|-------|----------|--------|
| Path traversal via `output_name` | **High** | User-supplied `output_name` used directly in `os.path.join(LORA_DIR, output_name)` without `safe_path()` validation; can write outside intended directory |
| Runs as root in container | Low | Dockerfile does not create a non-root user (unlike forge) |
| `fp16=True` hardcoded | Fragility | Fails on GPUs without FP16 support; suboptimal on Ampere+ (BF16 preferred) |
| No training progress updates | UX gap | Progress stays at 0 until completion, then jumps to 100 |
| `list_models()` only lists files | Functional gap | Misses directory-based HuggingFace models that Unsloth typically uses |
| No eval/validation | Functional gap | No eval dataset, no loss monitoring, no LoRA quality comparison |
| No resume support | Functional gap | Interrupted training cannot be continued |
| "Alpaca format" claim unsupported | Doc inaccuracy | Help text claims Alpaca support but no formatting function exists |

### Dependencies

Runtime: Flask 3.0.x, gunicorn 22.x, PyTorch, Unsloth, Transformers, TRL, PEFT, CUDA 12.2

---

## wm_flow.py — Flow Editor (38 lines)

### What It Does

Configuration-only wrapper around [Flowise](https://flowiseai.com/), a pre-built visual AI flow editor.

### Strengths

- Simplest possible plugin implementation — pure configuration, no custom code
- Demonstrates the plugin system's ability to wrap third-party images

### Issues Found

| Issue | Severity | Detail |
|-------|----------|--------|
| Hardcoded credentials | Medium | `FLOWISE_USERNAME=wickerman`, `FLOWISE_PASSWORD=wickerman` baked into manifest |
| Unpinned image tag | Fragility | `flowiseai/flowise:latest` — not reproducible, can break on upstream changes |

---

## Cross-Cutting Findings

### The Embedded Source Code Pattern

Every build-from-source plugin embeds its complete application as Python string literals. This is the single most impactful architectural decision in the plugin system:

- **No static analysis**: Linters, type checkers, and formatters cannot process code inside strings
- **No IDE support**: No autocomplete, go-to-definition, or refactoring for the majority of runtime code
- **No unit testing**: Embedded code cannot be tested without first extracting it to files
- **Debugging mismatch**: Runtime error line numbers don't match manifest file line numbers
- **Merge pain**: Diffs of embedded code are hard to review in version control

The trade-off is distribution simplicity — the entire system is two Python files plus a plugin package.

### Authentication

Zero authentication exists anywhere in the plugin system. All APIs are fully open. Combined with wm-llama's `Access-Control-Allow-Origin: *`, any website visited in the user's browser can interact with every service. This is acceptable for a strictly-localhost deployment but becomes a significant risk on any shared network.

### Other Patterns

- **No type hints** across any plugin (consistent but limits tooling)
- **`safe_path()` duplicated** identically in forge and trainer (separate containers, so runtime dedup isn't possible, but development-time consistency suffers)
- **Version string drift**: `__init__.py` and `wm_flow.py` say `v5.1.0`; `wm_chat.py` says `v5.2.0`
- **No automated tests** for any plugin — neither manifest validation nor embedded application testing
- **Node API pattern** is consistent across chat/forge/trainer — good for flow editor composability

### Vulnerability Summary

| # | Plugin | Issue | Severity |
|---|--------|-------|----------|
| 1 | wm_trainer | Path traversal via `output_name` | High |
| 2 | wm_forge | Arbitrary code execution, no auth | High (by design) |
| 3 | All | No authentication on any endpoint | High (LAN exposure) |
| 4 | wm_llama | Path traversal in static file serving | Medium |
| 5 | wm_llama | CORS `*` allows cross-origin API access | Medium |
| 6 | wm_llama | Mutable EMBED_DIM causes silent RAG corruption | Medium |
| 7 | wm_forge | XSS in file listing via unescaped filenames | Medium |
| 8 | wm_flow | Hardcoded default credentials | Medium |
| 9 | wm_trainer | Runs as root in container | Low |
| 10 | wm_llama | Bare `except:` swallows critical exceptions | Low |
