# Models Directory Review

> Independent third-party review — code and documentation examination only, no installation or testing.
> Date: 2026-03-21 | Reviewer: Claude Opus 4.6 | Codebase: wickerman-os @ 84e5170

---

## Contents

This directory contains only a `README.md` placeholder instructing users to place `.gguf` model files here. The files are gitignored (`.gitignore` excludes `models/*.gguf`, `models/*.bin`, `models/*.part`).

## Purpose

During installation, `wickermaninstall.py` copies any `.gguf` files from this directory into `~/WickermanSupport/models/`, which is mounted as a Docker volume into the `wm-llama` container.

## Observations

- The README recommends three specific models (Phi-4 Mini, Qwen2.5 Coder, Llama 3.2) with download sizes. These match the main project README.
- The `.gitignore` correctly prevents large binary files from being committed.
- There is no checksum validation of model files during the copy. Corrupted downloads would be silently deployed.
- No manifest or metadata file tracks which models are expected or their SHA256 hashes.
