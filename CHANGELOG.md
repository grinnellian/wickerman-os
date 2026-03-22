# Changelog

All notable changes to Wickerman OS are documented here. Each entry explains not just *what* changed but *why* — what problem the change solves and what principle it follows. The goal is to make the project's evolution understandable to anyone reading it.

---

## [Unreleased] — Beta 2 Standardization

This release focuses on bringing the project from "working prototype" to "standard software project." The original code is impressively functional — the changes here are about making it easier to maintain, safer to run, and accessible to contributors.

### Project Structure: Extracting Embedded Code

**What changed:** All runtime source code was extracted from Python string constants into real files under a new `src/` directory. The original files (`wickerman_support.py` and the plugin files) now read from those files at import time using `Path.read_text()` instead of containing the code inline.

**Why this matters:** The original approach — storing entire applications as string literals inside Python variables — is a clever distribution trick (two files to clone, one command to install). But it has a major downside: your editor, linter, and testing tools can't see inside string constants. They can't catch typos, suggest completions, or run tests on code that lives inside a string. By extracting to real files, every standard Python tool suddenly works. The installer still produces identical output — we verified this byte-for-byte.

**The principle:** "Code should be in files, not in strings." When code lives in its natural form, the entire ecosystem of development tools can help you.

### Project Tooling

**What changed:** Added `pyproject.toml`, `Makefile`, `.editorconfig`, and GitHub Actions CI.

**Why this matters:**
- **`pyproject.toml`** is the standard way to define a Python project. It tells tools like pip, pytest, ruff, and mypy how to work with your code. Before this, the project had no formal identity as a Python package — it was just loose files.
- **`Makefile`** gives everyone the same commands: `make test`, `make lint`, `make format`. No one has to remember which flags to pass. This is especially helpful when multiple people work on a project.
- **`.editorconfig`** ensures consistent whitespace (tabs vs spaces, line endings) across different editors. Inconsistent whitespace creates noisy diffs that obscure real changes.
- **GitHub Actions CI** runs the linter and tests automatically on every push and pull request. This catches mistakes before they reach the main branch. It's like a robot code reviewer that never sleeps.

**The principle:** "Automate the boring stuff." Humans forget to run the linter. Machines don't.

### Test Suite

**What changed:** Added four test files covering plugin schema validation, core utility functions, extraction fidelity, and the agent pipeline.

**Why this matters:** Tests serve two purposes. First, they catch bugs — if you change `safe_path()` and break it, the test fails immediately instead of failing silently in production. Second, and more importantly for this project, tests *document intent*. When someone reads `test_traversal_blocked`, they understand exactly what `safe_path()` is supposed to prevent. The tests were written *before* any behavioral changes were made, following the principle of "test first, change second" — this ensures we preserved the original author's intent.

**What's tested:**
- `safe_path()` — prevents users from accessing files outside allowed directories (path traversal attacks)
- `_conv_path()` — validates conversation IDs contain only safe characters
- `parse_hf_input()` — correctly extracts HuggingFace repo IDs from URLs and text
- `_build_cmd()` — constructs llama.cpp command-line arguments from a settings dictionary
- `_resolve_model()` — finds the right model by alias, filename, or fuzzy match
- `resolve_volume()` — substitutes volume path tokens like `{models}` and `{self}`
- `_apply_agent_pipeline()` — the system prompt injection and settings merging logic
- `chunk_messages()` — the RAG text chunking with overlap

**The principle:** "Tests are a safety net that lets you change code with confidence."

### Security Fixes

These are the most important changes in this release. None of them change how the system works when used normally — they only block things that *shouldn't* happen.

#### Path Traversal Fixes

**What changed:** Three places where user-supplied file paths could escape their intended directories were fixed.

**What's a path traversal?** If a user supplies the filename `../../../etc/passwd`, and the code naively joins it with a base directory like `/workspace`, the result is `/etc/passwd` — completely outside the intended directory. The `safe_path()` function already existed in the forge and chat plugins (nice work!), but two places were missing it:

1. **wm_trainer `output_name`**: When saving a trained LoRA adapter, the user-supplied output name was used directly in `os.path.join(LORA_DIR, output_name)`. A malicious name like `../../etc/cron.d/evil` could write files anywhere. Fixed by running it through `safe_path()`.

2. **wm_llama static file serving**: The URL path was stripped of leading slashes with `lstrip('/')`, but `os.path.join` can still resolve `..` sequences. Fixed by checking that the resolved path starts with the public directory using `os.path.realpath()`.

3. **`resolve_volume()` in the dashboard**: Plugin manifests specify volume mounts using tokens like `{self}`. After token substitution, the resolved path wasn't validated. A malicious plugin manifest could mount arbitrary host directories. Fixed by checking resolved paths stay within the support or install directories.

**The principle:** "Never trust user input." Even when the user is *you* — code that runs on a network can receive input from anywhere.

#### Network Hardening

**What changed:**
- **Nginx now binds to `127.0.0.1:80`** instead of `0.0.0.0:80`. The difference: `0.0.0.0` means "listen on all network interfaces," which makes the system accessible to every device on your local network. `127.0.0.1` means "localhost only" — only the machine running Wickerman can access it. If you *want* LAN access, you can change this, but it shouldn't be the default.

- **Storage secret is now randomly generated** instead of hardcoded as `"wm-secret"`. NiceGUI uses this value to sign session cookies. A hardcoded secret means anyone who reads the source code can forge sessions. Now a random 64-character hex string is generated on first run and saved to a file.

- **CORS origin is now configurable** instead of `*`. CORS (Cross-Origin Resource Sharing) controls which websites can make API calls to your server. `*` means "any website in the world." This meant if you visited a malicious webpage while Wickerman was running, that page could silently call your Model Router API. Now it defaults to localhost variants, configurable via the `CORS_ORIGINS` environment variable.

**The principle:** "Secure by default, open by choice."

#### Exception Handling

**What changed:** Replaced 8 instances of bare `except:` with `except Exception:`.

**Why this matters:** In Python, `except:` (without specifying a type) catches *everything*, including `KeyboardInterrupt` (Ctrl+C) and `SystemExit` (the process trying to shut down). This means pressing Ctrl+C might get silently swallowed instead of stopping the program. `except Exception:` catches all "normal" errors while still allowing the process to be interrupted or shut down. It's a small change with no impact on normal operation, but it makes the system behave correctly in edge cases.

**The principle:** "Catch what you mean to catch, nothing more."

#### EMBED_DIM Fix

**What changed:** The RAG system's embedding dimension is now stored per-index in SQLite metadata instead of in a mutable global variable.

**What was the bug?** The Model Router kept a global variable `EMBED_DIM = 384` that tracked the dimension of embedding vectors. When an embedding came back with a different dimension (because you loaded a different model), it silently updated this global. But FAISS indices are built for a specific dimension — you can't search a 384-dimensional index with a 768-dimensional vector. The old code would silently produce garbage results. Now each index records its dimension, and a mismatch triggers a rebuild with a clear log message.

**The principle:** "Global mutable state is a bug waiting to happen." When two things share a variable and either can change it, you get surprises.

### Bug Fixes

- **`export_project()` in Code Forge** now actually uses the `files` parameter. Previously it accepted a list of files but then ignored it and zipped the entire workspace. Now it zips only the specified files, using `safe_path()` to validate each one.
- **`stop.sh`** now removes stopped plugin containers instead of just stopping them. Without this, stopped containers accumulated on disk over repeated stop/start cycles.
- **`list_models()` in the Trainer** now detects directory-based HuggingFace models (which contain `.bin`/`.safetensors` files) in addition to single GGUF files.
- **Flowise image pinned to version 2.2.7** instead of `:latest`. Using `:latest` means your system can break without warning when the upstream project releases a new version. Pinning ensures reproducible builds.
- **Version strings unified** to v5.2.0 across all files. `__init__.py` and `wm_flow.py` still said v5.1.0.
- **Unused import removed:** `from collections import deque` was imported but never used in the dashboard.

### Code Quality

- **Shared utilities:** Created `src/shared/security.py` with the canonical `safe_path()` implementation and `src/shared/version.py` as the single source of truth for the version string. Having one definition referenced everywhere means you can't accidentally have different versions of the same function.
- **DRY (Don't Repeat Yourself):** Extracted duplicate git-init blocks in the installer into a reusable `init_git_repo()` helper function.
- **Route table refactor:** The Model Router's `do_GET` method was an 80-line chain of `elif` statements. Each route is now a separate method dispatched via a dictionary lookup. Same behavior, but each route is independently readable and testable.

### Developer Experience

- **Dev container:** Added `.devcontainer/` configuration for VS Code and a standalone `docker-compose.dev.yml`. Both provide Python 3.11, pytest, ruff, mypy, and Claude Code pre-installed in an isolated Docker environment. Uses the same Dockerfile — VS Code's "Reopen in Container" or `docker compose -f docker-compose.dev.yml up` from any terminal.
- **Network firewall:** The dev container includes an outbound allowlist firewall (`init-firewall.sh`). This is the compensating control for running Claude Code with `--dangerously-skip-permissions`: even if code runs arbitrary commands, it can only reach whitelisted domains (Anthropic API, GitHub, npm, PyPI). All other outbound traffic is blocked with an immediate REJECT. The allowlist is a simple bash array at the top of the script — easy to audit and edit.
- **CI pipeline:** GitHub Actions runs ruff (linting), mypy (type checking), and pytest (149 tests) on every push and PR to `main` and `beta2-standardization`. Original author's code in `src/` is excluded from linting — style changes will be proposed separately, not mixed in with structural work. A CI status badge on the README gives instant visibility into build health.
- **mypy passing clean:** Fixed a duplicate module name collision (`app` appeared in both `src/downloader/` and `src/plugins/chat/`) by enabling `explicit_package_bases` in the mypy config. Added `types-requests` stubs and minimal type annotations to three unannotated module-level dicts. mypy now reports zero errors across all 16 source files.
- **gh CLI:** Installed in the dev container so Claude Code and developers can create issues, manage PRs, and push code without leaving the container. Auth is handled via `GH_TOKEN` env var forwarded from the host — use a fine-grained personal access token scoped to just this repo for minimum blast radius.
- **Git credential forwarding:** A minimal credential helper reads `GH_TOKEN` from the environment at push time. No token stored on disk inside the container.
- **CONTRIBUTING.md:** Documents project structure, development setup (three paths: VS Code, standalone Docker, local), and code style expectations.
- **This changelog:** Explains every change and the reasoning behind it.

### Documentation

- **REVIEW.md:** Independent third-party code review at top level and per-directory, examining architecture, security, code quality, and completeness.
- **BETA2_PLAN.md:** Phased standardization plan with GitHub issue tracking (18 issues created, 15 closed).
- **EXTRACTION_MAP.md:** Complete map of how embedded source code flows from string constants to runtime files.
- **README.md:** Updated with development setup instructions and dev container quickstart.

---

## [5.2.0] — 2026-03-21

Initial public release by Tabulanis. Features: agent orchestration with system prompts and per-agent RAG memory, multi-model local inference via llama.cpp, remote provider support (OpenAI, Anthropic, Gemini), multi-conversation chat UI, visual pipeline editor (Flowise), LoRA fine-tuning (Unsloth), code generation sandbox, NiceGUI dashboard with system monitoring and git version control, single-file installer.
