# Wickerman OS — Beta 2 Standardization Plan

> Working branch: `beta2-standardization`
> Started: 2026-03-21
> Goal: Move from "functional prototype with non-standard structure" to "standard Python project with tests, CI, and maintainable code"
> Scope: Beta 2 — not production. Focus on structural soundness and preserving author intent.

---

## Guiding Principles

1. **Preserve author intent first.** Before restructuring anything, have tests that prove the current behavior. The embedded code pattern is unusual but deliberate — understand it fully before changing it.
2. **Commit early, commit often.** Every meaningful step gets its own commit.
3. **One structural change at a time.** Don't refactor code quality while also moving files. Separate concerns in separate commits/PRs.
4. **Beta 2, not production.** Fix real bugs and structural issues. Don't gold-plate.

---

## Phase 0: Foundation & Tooling
> Priority: P0 — everything else depends on this

### 0.1 — Project tooling setup
- [ ] Create `pyproject.toml` with project metadata, dev dependencies (pytest, ruff, mypy)
- [ ] Create `Makefile` or `justfile` for common dev commands (test, lint, format)
- [ ] Add `.github/workflows/ci.yml` stub (lint + test)
- **Depends on**: nothing
- **Issue**: [#1](https://github.com/grinnellian/wickerman-os/issues/1)

### 0.2 — Map the extraction pipeline
- [ ] Document exactly what the installer does: which string constants become which files, where
- [ ] Create a manifest/map: `{string_constant_name → target_path → container}`
- [ ] Verify the map by reading installer logic line by line
- **Depends on**: nothing
- **Issue**: [#2](https://github.com/grinnellian/wickerman-os/issues/2)

### 0.3 — Extract embedded source to real files
- [ ] Create a `src/` tree mirroring the runtime directory structure
- [ ] Move each string constant's content into its actual file (e.g., `src/core_app/main.py`, `src/downloader/app.py`, etc.)
- [ ] Replace string constants in `wickerman_support.py` and plugin files with file reads (`Path(...).read_text()`)
- [ ] Verify installer still produces identical output (byte-for-byte comparison of generated files)
- **Depends on**: 0.2 (#2)
- **Issue**: [#3](https://github.com/grinnellian/wickerman-os/issues/3)

---

## Phase 1: Test Coverage (Preserve Intent)
> Priority: P0 — required before any behavioral changes

### 1.1 — Extraction fidelity tests
- [ ] Test that the installer produces the same output files with the new file-read approach as with the old string constants
- [ ] Snapshot the current generated `docker-compose.yml`, `start.sh`, nginx conf, and all plugin manifests
- [ ] Assert generated output matches snapshots
- **Depends on**: 0.3 (#3)
- **Issue**: [#4](https://github.com/grinnellian/wickerman-os/issues/4)

### 1.2 — Unit tests for core utilities
- [ ] Test `safe_path()` (both forge and trainer implementations)
- [ ] Test `resolve_volume()` token substitution
- [ ] Test `_conv_path()` and conversation ID validation
- [ ] Test `_resolve_model()` alias/fuzzy matching
- [ ] Test `_build_cmd()` CLI flag generation
- [ ] Test `parse_hf_input()` URL/repo parsing
- **Depends on**: 0.1 (#1), 0.3 (#3)
- **Issue**: [#5](https://github.com/grinnellian/wickerman-os/issues/5)

### 1.3 — Unit tests for agent pipeline
- [ ] Test `_apply_agent_pipeline()` — system prompt injection, trimming, RAG injection
- [ ] Test RAG operations: chunking, embedding dimension handling, FAISS add/search
- [ ] Test provider proxy routing (_proxy_local, _proxy_openai, _proxy_anthropic, _proxy_google)
- **Depends on**: 0.3 (#3), 1.2 (#5)
- **Issue**: [#6](https://github.com/grinnellian/wickerman-os/issues/6)

### 1.4 — Plugin manifest schema validation
- [ ] Define expected manifest schema (required keys, types, valid values)
- [ ] Test all 5 plugin manifests against the schema
- [ ] Test volume token resolution for each plugin
- **Depends on**: 0.1 (#1)
- **Issue**: [#7](https://github.com/grinnellian/wickerman-os/issues/7)

---

## Phase 2: Security Fixes
> Priority: P1 — real vulnerabilities identified in review

### 2.1 — Fix path traversals
- [ ] **wm_trainer**: Apply `safe_path()` to `output_name` parameter (1-line fix)
- [ ] **wm_llama**: Validate resolved static file paths start with `PUBLIC_DIR`
- [ ] **wickerman_support.py**: Validate `resolve_volume()` output stays within support directory
- [ ] Add tests for each fix (traversal attempts must fail)
- **Depends on**: 1.2 (#5)
- **Issue**: [#8](https://github.com/grinnellian/wickerman-os/issues/8)

### 2.2 — Network exposure defaults
- [ ] Bind nginx to `127.0.0.1:80` instead of `0.0.0.0:80` in compose generation
- [ ] Generate random `storage_secret` at install time, persist to file
- [ ] Document how to consciously enable LAN access
- **Depends on**: 1.1 (#4)
- **Issue**: [#9](https://github.com/grinnellian/wickerman-os/issues/9)

### 2.3 — Fix CORS and session security
- [ ] Replace `Access-Control-Allow-Origin: *` with configurable allowed origins (default: localhost variants)
- [ ] Replace bare `except:` with `except Exception:` across all files
- **Depends on**: 0.3 (#3)
- **Issue**: [#10](https://github.com/grinnellian/wickerman-os/issues/10)

### 2.4 — Fix EMBED_DIM mutation
- [ ] Store embedding dimension per FAISS index in SQLite metadata
- [ ] Validate dimension on search; rebuild index if mismatch detected
- [ ] Add test for dimension mismatch scenario
- **Depends on**: 1.3 (#6)
- **Issue**: [#11](https://github.com/grinnellian/wickerman-os/issues/11)

---

## Phase 3: Code Quality
> Priority: P2 — maintainability improvements, no behavioral changes

### 3.1 — Linting and formatting baseline
- [ ] Run ruff on extracted source files, fix auto-fixable issues
- [ ] Establish ruff config in `pyproject.toml`
- [ ] Fix unused imports (e.g., `deque` in support)
- **Depends on**: 0.3 (#3)
- **Issue**: [#12](https://github.com/grinnellian/wickerman-os/issues/12)

### 3.2 — Type hints on public interfaces
- [ ] Add type annotations to all public functions in extracted source
- [ ] Run mypy in basic mode, fix errors
- [ ] Do NOT add hints to private/internal helpers unless trivial
- **Depends on**: 3.1 (#12)
- **Issue**: [#13](https://github.com/grinnellian/wickerman-os/issues/13)

### 3.3 — Break up monolithic functions
- [ ] Extract dashboard `index()` into component functions
- [ ] Add routing table to wm_llama `do_GET`/`do_POST` (replace elif chains)
- [ ] Extract duplicated git-init blocks in installer into helper
- [ ] Extract shared chat/node logic in wm_chat into helper
- **Depends on**: 1.1 (#4), 1.2 (#5), 1.3 (#6)
- **Issue**: [#14](https://github.com/grinnellian/wickerman-os/issues/14)

### 3.4 — Fix DRY violations and version drift
- [ ] Unify `safe_path()` into a shared utility (even if copied into each container at build time)
- [ ] Fix version string inconsistencies (v5.1.0 vs v5.2.0)
- [ ] Define version in one place, reference it everywhere
- **Depends on**: 0.3 (#3)
- **Issue**: [#15](https://github.com/grinnellian/wickerman-os/issues/15)

### 3.5 — Fix remaining bugs
- [ ] Fix `export_project()` ignoring `files` parameter in wm_forge
- [ ] Fix stop.sh not removing stopped plugin containers
- [ ] Fix `list_models()` in wm_trainer to support directory-based models
- [ ] Pin Flowise image version
- **Depends on**: 1.1 (#4)
- **Issue**: [#16](https://github.com/grinnellian/wickerman-os/issues/16)

---

## Phase 4: Project Infrastructure
> Priority: P2 — quality of life for ongoing development

### 4.1 — CI/CD pipeline
- [ ] GitHub Actions: lint (ruff), type check (mypy), test (pytest) on push/PR
- [ ] Add status badges to README
- **Depends on**: 0.1 (#1), 1.2 (#5)
- **Issue**: [#17](https://github.com/grinnellian/wickerman-os/issues/17)

### 4.2 — Documentation updates
- [ ] Create CHANGELOG.md (starting with v5.2.0 baseline and beta 2 changes)
- [ ] Create CONTRIBUTING.md with dev setup instructions
- [ ] Add troubleshooting section to README
- [ ] Document security considerations
- **Depends on**: all phases substantively complete
- **Issue**: [#18](https://github.com/grinnellian/wickerman-os/issues/18)

---

## Dependency Graph

```
Phase 0: Foundation
  #1  0.1 Tooling ──────────────────────────────────┐
  #2  0.2 Map extraction ──► #3 0.3 Extract ────────┤
                                                     │
Phase 1: Tests                                       │
  #7  1.4 Schema tests ◄────────────────── #1 ◄─────┤
  #4  1.1 Fidelity tests ◄────────────────── #3 ◄───┤
  #5  1.2 Unit tests ◄──────────────── #1 + #3      │
  #6  1.3 Pipeline tests ◄──────────── #3 + #5      │
                                                      │
Phase 2: Security                                     │
  #8  2.1 Path traversals ◄──────────────── #5      │
  #9  2.2 Network defaults ◄─────────────── #4      │
  #10 2.3 CORS / exceptions ◄────────────── #3      │
  #11 2.4 EMBED_DIM ◄──────────────────── #6        │
                                                      │
Phase 3: Code Quality                                 │
  #12 3.1 Lint baseline ◄────────────────── #3      │
  #13 3.2 Type hints ◄──────────────────── #12      │
  #14 3.3 Refactor monoliths ◄── #4 + #5 + #6      │
  #15 3.4 DRY / versions ◄──────────────── #3       │
  #16 3.5 Bug fixes ◄───────────────────── #4       │
                                                      │
Phase 4: Infrastructure                               │
  #17 4.1 CI/CD ◄────────────────────── #1 + #5     │
  #18 4.2 Docs ◄────────────────── all phases        │
```

---

## Future Milestones (Sketch)

These are out of scope for beta 2 but provide directional scaffolding:

### Beta 3 — "Hardened Local"
- Authentication layer (nginx basic auth or token-based)
- HTTPS support (self-signed cert generation)
- Streaming support for chat and LLM endpoints
- Health check endpoints for all services
- Structured logging with correlation IDs

### RC 1 — "Contributor Ready"
- Plugin SDK with formal interface (abstract base class or Protocol)
- Plugin autodiscovery (no manual __init__.py editing)
- Integration test suite (Docker-based, spins up real containers)
- API documentation (OpenAPI spec)
- Performance benchmarks

### 1.0 — "Stable"
- Semantic versioning with release automation
- Backward compatibility guarantees for plugin manifests
- Migration tooling for config/data across versions
- Security audit by external party
- Multi-user support with RBAC (if needed)
