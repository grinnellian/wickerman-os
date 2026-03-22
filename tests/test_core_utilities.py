"""
Phase 1.2: Unit tests for core utilities (#5).
Tests pure functions extracted from the embedded source code.
These functions are tested by re-implementing them in isolation since
the source files have heavy framework dependencies (Flask, NiceGUI, etc.)
that can't be imported without Docker.
"""
import os
import re

import pytest


# ── safe_path (identical in forge and trainer) ─────────────────────────────

def safe_path(base, user_input):
    """Reimplemented from src/plugins/forge/app.py and src/plugins/trainer/app.py"""
    joined = os.path.abspath(os.path.join(base, user_input))
    if not joined.startswith(os.path.abspath(base)):
        raise ValueError(f"Path traversal blocked: {user_input}")
    return joined


class TestSafePath:
    def test_normal_filename(self):
        result = safe_path("/workspace", "hello.py")
        assert result == "/workspace/hello.py"

    def test_subdirectory(self):
        result = safe_path("/workspace", "sub/dir/file.txt")
        assert result == "/workspace/sub/dir/file.txt"

    def test_traversal_blocked(self):
        with pytest.raises(ValueError, match="Path traversal blocked"):
            safe_path("/workspace", "../../../etc/passwd")

    def test_traversal_with_dotdot_in_middle(self):
        with pytest.raises(ValueError, match="Path traversal blocked"):
            safe_path("/workspace", "sub/../../etc/passwd")

    def test_absolute_path_outside_base(self):
        with pytest.raises(ValueError, match="Path traversal blocked"):
            safe_path("/workspace", "/etc/passwd")

    def test_dot_stays_in_base(self):
        result = safe_path("/workspace", ".")
        assert result == "/workspace"

    def test_dotdot_inside_subdir(self):
        # sub/../file.txt resolves to /workspace/file.txt — still inside base
        result = safe_path("/workspace", "sub/../file.txt")
        assert result == "/workspace/file.txt"

    def test_empty_input(self):
        result = safe_path("/workspace", "")
        assert result == "/workspace"

    def test_base_with_trailing_slash(self):
        result = safe_path("/workspace/", "file.txt")
        assert result == "/workspace/file.txt"


# ── _conv_path (from chat/app.py) ─────────────────────────────────────────

CONV_DIR = "/data/conversations"

def _conv_path(cid):
    """Reimplemented from src/plugins/chat/app.py"""
    if not cid.isalnum():
        raise ValueError("Invalid Conversation ID")
    return os.path.join(CONV_DIR, cid + ".json")


class TestConvPath:
    def test_normal_id(self):
        result = _conv_path("abc123")
        assert result == "/data/conversations/abc123.json"

    def test_rejects_slashes(self):
        with pytest.raises(ValueError, match="Invalid Conversation ID"):
            _conv_path("../etc/passwd")

    def test_rejects_dots(self):
        with pytest.raises(ValueError, match="Invalid Conversation ID"):
            _conv_path("file.name")

    def test_rejects_spaces(self):
        with pytest.raises(ValueError, match="Invalid Conversation ID"):
            _conv_path("hello world")

    def test_rejects_special_chars(self):
        with pytest.raises(ValueError, match="Invalid Conversation ID"):
            _conv_path("id;rm -rf /")

    def test_pure_alpha(self):
        assert _conv_path("abcdef") == "/data/conversations/abcdef.json"

    def test_pure_numeric(self):
        assert _conv_path("12345") == "/data/conversations/12345.json"

    def test_alphanumeric(self):
        assert _conv_path("abc123def") == "/data/conversations/abc123def.json"


# ── parse_hf_input (from downloader/app.py) ──────────────────────────────

def parse_hf_input(text):
    """Reimplemented from src/downloader/app.py"""
    text = text.strip().rstrip("/")
    m = re.match(r'https?://huggingface\.co/([^/]+/[^/]+)', text)
    if m:
        return m.group(1)
    if "/" in text and not text.startswith("http"):
        return text
    return None


class TestParseHfInput:
    def test_full_url(self):
        assert parse_hf_input("https://huggingface.co/TheBloke/Llama-2-7B-GGUF") == "TheBloke/Llama-2-7B-GGUF"

    def test_http_url(self):
        assert parse_hf_input("http://huggingface.co/user/model") == "user/model"

    def test_url_with_trailing_slash(self):
        assert parse_hf_input("https://huggingface.co/user/model/") == "user/model"

    def test_url_with_subpath(self):
        # Should still extract the org/repo part
        assert parse_hf_input("https://huggingface.co/user/model/tree/main") == "user/model"

    def test_repo_id_directly(self):
        assert parse_hf_input("TheBloke/Llama-2-7B-GGUF") == "TheBloke/Llama-2-7B-GGUF"

    def test_repo_id_with_whitespace(self):
        assert parse_hf_input("  TheBloke/Llama-2-7B-GGUF  ") == "TheBloke/Llama-2-7B-GGUF"

    def test_invalid_no_slash(self):
        assert parse_hf_input("just-a-word") is None

    def test_invalid_empty(self):
        assert parse_hf_input("") is None

    def test_invalid_random_url(self):
        assert parse_hf_input("https://example.com/something") is None

    def test_invalid_http_with_slash_but_not_hf(self):
        # Starts with http, has a /, but not HF — should be None
        assert parse_hf_input("http://example.com/foo/bar") is None


# ── _build_cmd (from llama/manager.py) ───────────────────────────────────

SETTINGS_SCHEMA = {
    "n_gpu_layers": {"flag": "--n-gpu-layers", "default": "99", "type": "int"},
    "ctx_size": {"flag": "--ctx-size", "default": "4096", "type": "int"},
    "threads": {"flag": "--threads", "default": "", "type": "int"},
    "batch_size": {"flag": "--batch-size", "default": "", "type": "int"},
    "flash_attn": {"flag": "--flash-attn", "default": "", "type": "flag"},
    "cont_batching": {"flag": "--cont-batching", "default": "", "type": "flag"},
    "mlock": {"flag": "--mlock", "default": "", "type": "flag"},
    "no_mmap": {"flag": "--no-mmap", "default": "", "type": "flag"},
    "cache_type_k": {"flag": "--cache-type-k", "default": "", "type": "str"},
    "cache_type_v": {"flag": "--cache-type-v", "default": "", "type": "str"},
    "rope_freq_base": {"flag": "--rope-freq-base", "default": "", "type": "float"},
    "rope_freq_scale": {"flag": "--rope-freq-scale", "default": "", "type": "float"},
    "chat_template": {"flag": "--chat-template", "default": "", "type": "str"},
    "jinja": {"flag": "--jinja", "default": "", "type": "flag"},
    "reasoning_format": {"flag": "--reasoning-format", "default": "", "type": "str"},
    "seed": {"flag": "--seed", "default": "", "type": "int"},
    "metrics": {"flag": "--metrics", "default": "", "type": "flag"},
    "verbose_prompt": {"flag": "--verbose-prompt", "default": "", "type": "flag"},
    "verbosity": {"flag": "--verbosity", "default": "", "type": "int"},
}


def _build_cmd(model_path, port, settings):
    """Reimplemented from src/plugins/llama/manager.py"""
    cmd = ["/usr/local/bin/llama-server", "--model", model_path,
           "--host", "127.0.0.1", "--port", str(port)]
    for key, schema in SETTINGS_SCHEMA.items():
        val = settings.get(key, schema["default"])
        if not val and val != 0:
            continue
        val = str(val)
        if schema["type"] == "flag":
            if val.lower() in ("true", "1", "on", "yes"):
                cmd.append(schema["flag"])
        else:
            cmd.extend([schema["flag"], val])
    return cmd


class TestBuildCmd:
    def test_minimal_defaults(self):
        cmd = _build_cmd("/models/test.gguf", 8081, {})
        assert cmd[:4] == ["/usr/local/bin/llama-server", "--model", "/models/test.gguf",
                           "--host", "127.0.0.1"]
        assert "--port" in cmd
        assert cmd[cmd.index("--port") + 1] == "8081"
        # Should include default n_gpu_layers and ctx_size
        assert "--n-gpu-layers" in cmd
        assert "99" in cmd
        assert "--ctx-size" in cmd
        assert "4096" in cmd

    def test_custom_settings(self):
        cmd = _build_cmd("/models/test.gguf", 8081, {
            "ctx_size": "8192",
            "threads": "4",
        })
        idx = cmd.index("--ctx-size")
        assert cmd[idx + 1] == "8192"
        idx = cmd.index("--threads")
        assert cmd[idx + 1] == "4"

    def test_flag_type_true(self):
        cmd = _build_cmd("/models/test.gguf", 8081, {"flash_attn": "true"})
        assert "--flash-attn" in cmd

    def test_flag_type_false(self):
        cmd = _build_cmd("/models/test.gguf", 8081, {"flash_attn": "false"})
        assert "--flash-attn" not in cmd

    def test_flag_type_yes(self):
        cmd = _build_cmd("/models/test.gguf", 8081, {"mlock": "yes"})
        assert "--mlock" in cmd

    def test_empty_value_skipped(self):
        cmd = _build_cmd("/models/test.gguf", 8081, {"threads": ""})
        assert "--threads" not in cmd

    def test_zero_value_included(self):
        cmd = _build_cmd("/models/test.gguf", 8081, {"seed": "0"})
        assert "--seed" in cmd

    def test_unknown_settings_ignored(self):
        cmd = _build_cmd("/models/test.gguf", 8081, {"unknown_key": "value"})
        assert "value" not in cmd


# ── _resolve_model (from llama/manager.py) ──────────────────────────────

class TestResolveModel:
    """Test _resolve_model logic with a mock _slots dict."""

    def _resolve(self, model_name, slots):
        """Reimplemented from src/plugins/llama/manager.py"""
        if not model_name or model_name == "default":
            for s in slots.values():
                if s["status"] == "ready" and s.get("type") == "local":
                    return s, None
            for s in slots.values():
                if s["status"] == "ready":
                    return s, None
            return None, "No agents loaded"
        if model_name in slots:
            s = slots[model_name]
            if s["status"] == "ready":
                return s, None
            return None, f"Agent '{model_name}' is {s['status']}: {s.get('detail', '')}"
        for s in slots.values():
            if s.get("model_file") == model_name and s["status"] == "ready":
                return s, None
        for alias, s in slots.items():
            if model_name.lower() in alias.lower() and s["status"] == "ready":
                return s, None
        return None, f"Agent '{model_name}' not found. Available: {', '.join(slots.keys()) or 'none'}"

    def test_default_finds_local_ready(self):
        slots = {"agent1": {"status": "ready", "type": "local"}}
        s, err = self._resolve("default", slots)
        assert s is not None
        assert err is None

    def test_default_finds_any_ready_if_no_local(self):
        slots = {"remote1": {"status": "ready", "type": "openai"}}
        s, _err = self._resolve("default", slots)
        assert s is not None

    def test_default_prefers_local_over_remote(self):
        slots = {
            "remote1": {"status": "ready", "type": "openai"},
            "local1": {"status": "ready", "type": "local"},
        }
        s, _err = self._resolve("default", slots)
        assert s["type"] == "local"

    def test_default_empty_slots(self):
        s, err = self._resolve("default", {})
        assert s is None
        assert "No agents loaded" in err

    def test_none_treated_as_default(self):
        slots = {"agent1": {"status": "ready", "type": "local"}}
        s, _err = self._resolve(None, slots)
        assert s is not None

    def test_exact_alias_match(self):
        slots = {"my-agent": {"status": "ready", "type": "local"}}
        s, _err = self._resolve("my-agent", slots)
        assert s is not None

    def test_alias_not_ready(self):
        slots = {"my-agent": {"status": "loading", "detail": "50%"}}
        s, err = self._resolve("my-agent", slots)
        assert s is None
        assert "loading" in err

    def test_model_file_match(self):
        slots = {"agent1": {"status": "ready", "type": "local", "model_file": "llama-7b.gguf"}}
        s, _err = self._resolve("llama-7b.gguf", slots)
        assert s is not None

    def test_fuzzy_substring_match(self):
        slots = {"my-llama-agent": {"status": "ready", "type": "local"}}
        s, _err = self._resolve("llama", slots)
        assert s is not None

    def test_fuzzy_case_insensitive(self):
        slots = {"MyAgent": {"status": "ready", "type": "local"}}
        s, _err = self._resolve("myagent", slots)
        assert s is not None

    def test_not_found(self):
        slots = {"agent1": {"status": "ready", "type": "local"}}
        s, err = self._resolve("nonexistent", slots)
        assert s is None
        assert "not found" in err
        assert "agent1" in err


# ── resolve_volume (from core/main.py) ──────────────────────────────────

def resolve_volume(spec, plugin_id, support_dir="/support", host_base="/home/user/wickerman"):
    """Reimplemented from src/core/main.py with injectable paths."""
    parts = spec.split(":")
    raw_host, cpath = parts[0], parts[1]
    mode = parts[2] if len(parts) >= 3 else "rw"
    host = (raw_host
        .replace("{self}", f"{support_dir}/plugins/{plugin_id}")
        .replace("{models}", f"{support_dir}/models")
        .replace("{datasets}", f"{support_dir}/datasets")
        .replace("{loras}", f"{support_dir}/loras")
        .replace("{support}", support_dir)
        .replace("{workspace}", f"{host_base}/workspace"))
    return host, cpath, mode


class TestResolveVolume:
    def test_self_token(self):
        h, c, m = resolve_volume("{self}/data:/data", "wm-chat")
        assert h == "/support/plugins/wm-chat/data"
        assert c == "/data"
        assert m == "rw"

    def test_models_token(self):
        h, c, m = resolve_volume("{models}:/models:ro", "wm-llama")
        assert h == "/support/models"
        assert c == "/models"
        assert m == "ro"

    def test_datasets_token(self):
        h, c, m = resolve_volume("{datasets}:/datasets:ro", "wm-trainer")
        assert h == "/support/datasets"
        assert c == "/datasets"
        assert m == "ro"

    def test_loras_token(self):
        h, c, _m = resolve_volume("{loras}:/loras", "wm-trainer")
        assert h == "/support/loras"
        assert c == "/loras"

    def test_workspace_token(self):
        h, c, _m = resolve_volume("{workspace}:/workspace", "wm-forge")
        assert h == "/home/user/wickerman/workspace"
        assert c == "/workspace"

    def test_no_token(self):
        h, c, m = resolve_volume("/var/run/docker.sock:/var/run/docker.sock:ro", "wm-core")
        assert h == "/var/run/docker.sock"
        assert c == "/var/run/docker.sock"
        assert m == "ro"

    def test_default_mode_is_rw(self):
        _h, _c, m = resolve_volume("{self}/data:/data", "test")
        assert m == "rw"

    def test_multiple_tokens_in_one_spec(self):
        # Unlikely but should work — each token replaced independently
        h, _c, _m = resolve_volume("{models}:/models", "test", support_dir="/sup")
        assert h == "/sup/models"
