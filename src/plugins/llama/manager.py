#!/usr/bin/env python3
# Wickerman Model Router v3.0
# Agent orchestration layer: local models + remote APIs + RAG + system prompts.
# Each slot is a self-contained agent. Callers just pick an alias.
import os, sys, json, glob, signal, subprocess, threading, time, socket, atexit, re, sqlite3
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError
import numpy as np
import faiss
import tiktoken

MODEL_DIR = os.environ.get("MODEL_DIR", "/models")
GPU_LAYERS = os.environ.get("GPU_LAYERS", "99")
CTX_SIZE = os.environ.get("CTX_SIZE", "4096")
LISTEN_PORT = 8080
PUBLIC_DIR = "/opt/llama.cpp/examples/server/public"
CONFIG_FILE = "/data/router_config.json"
PROVIDERS_FILE = "/data/providers.json"
RAG_DIR = "/data/rag"
os.makedirs(RAG_DIR, exist_ok=True)

_slots = {}
_slots_lock = threading.Lock()
_enc = tiktoken.get_encoding("cl100k_base")
EMBED_DIM = 384
CHUNK_SIZE = 200
CHUNK_OVERLAP = 50

# ── Utilities ────────────────────────────────────────────────
def _get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def _auto_name(filename):
    name = filename
    if name.endswith(".gguf"): name = name[:-5]
    name = re.sub(r'[-_][QqIi][0-9]+[-_][A-Za-z0-9_]+$', '', name)
    name = name.strip('-_').lower().replace(' ', '-').replace('.', '-')
    return name

def human_size(b):
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024: return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} PB"

def count_tokens(text):
    return len(_enc.encode(text))

def count_messages_tokens(messages):
    total = 0
    for m in messages: total += count_tokens(m.get("content", "")) + 4
    return total

def trim_messages(messages, ctx_size, reserve_pct=0.8):
    max_tokens = int(ctx_size * reserve_pct)
    total = count_messages_tokens(messages)
    if total <= max_tokens: return messages, [], total, ctx_size
    trimmed = []
    keep = list(messages)
    sys_msg = None
    if keep and keep[0].get("role") == "system":
        sys_msg = keep.pop(0)
    current_tokens = count_messages_tokens(([sys_msg] if sys_msg else []) + keep)
    while current_tokens > max_tokens and len(keep) > 2:
        popped = keep.pop(0)
        trimmed.append(popped)
        current_tokens -= (count_tokens(popped.get("content", "")) + 4)
    result = ([sys_msg] if sys_msg else []) + keep
    return result, trimmed, current_tokens, ctx_size

def list_models():
    models = []
    loaded_files = {s["model_file"] for s in _slots.values() if s.get("type") == "local"}
    for f in sorted(glob.glob(os.path.join(MODEL_DIR, "*.gguf"))):
        name = os.path.basename(f)
        size = os.path.getsize(f)
        models.append({"name": name, "auto_name": _auto_name(name), "size": human_size(size),
                        "bytes": size, "estimated_vram_mb": int(size / 1024 / 1024 * 1.2),
                        "loaded": name in loaded_files})
    return models

def get_vram_info():
    try:
        import pynvml
        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem = pynvml.nvmlDeviceGetMemoryInfo(h)
        gpu_name = pynvml.nvmlDeviceGetName(h)
        if isinstance(gpu_name, bytes): gpu_name = gpu_name.decode()
        return {"gpu_name": gpu_name, "total_mb": mem.total // (1024*1024),
                "used_mb": mem.used // (1024*1024), "free_mb": mem.free // (1024*1024)}
    except: return {"gpu_name": "Unknown", "total_mb": 0, "used_mb": 0, "free_mb": 0}

# ── Settings schema ──────────────────────────────────────────
SETTINGS_SCHEMA = {
    "ctx_size": {"flag": "--ctx-size", "default": "4096", "type": "int"},
    "gpu_layers": {"flag": "--n-gpu-layers", "default": "99", "type": "int"},
    "threads": {"flag": "--threads", "default": "", "type": "int"},
    "batch_size": {"flag": "--batch-size", "default": "", "type": "int"},
    "ubatch_size": {"flag": "--ubatch-size", "default": "", "type": "int"},
    "flash_attn": {"flag": "-fa", "default": "", "type": "flag"},
    "parallel": {"flag": "--parallel", "default": "", "type": "int"},
    "no_mmap": {"flag": "--no-mmap", "default": "", "type": "flag"},
    "threads_batch": {"flag": "--threads-batch", "default": "", "type": "int"},
    "cont_batching": {"flag": "--cont-batching", "default": "", "type": "flag"},
    "cache_type_k": {"flag": "--cache-type-k", "default": "", "type": "str"},
    "cache_type_v": {"flag": "--cache-type-v", "default": "", "type": "str"},
    "no_context_shift": {"flag": "--no-context-shift", "default": "", "type": "flag"},
    "split_mode": {"flag": "--split-mode", "default": "", "type": "str"},
    "tensor_split": {"flag": "--tensor-split", "default": "", "type": "str"},
    "main_gpu": {"flag": "--main-gpu", "default": "", "type": "int"},
    "rope_scaling": {"flag": "--rope-scaling", "default": "", "type": "str"},
    "rope_freq_base": {"flag": "--rope-freq-base", "default": "", "type": "float"},
    "rope_freq_scale": {"flag": "--rope-freq-scale", "default": "", "type": "float"},
    "yarn_orig_ctx": {"flag": "--yarn-orig-ctx", "default": "", "type": "int"},
    "yarn_ext_factor": {"flag": "--yarn-ext-factor", "default": "", "type": "float"},
    "chat_template": {"flag": "--chat-template", "default": "", "type": "str"},
    "jinja": {"flag": "--jinja", "default": "", "type": "flag"},
    "reasoning_format": {"flag": "--reasoning-format", "default": "", "type": "str"},
    "seed": {"flag": "--seed", "default": "", "type": "int"},
    "metrics": {"flag": "--metrics", "default": "", "type": "flag"},
    "verbose_prompt": {"flag": "--verbose-prompt", "default": "", "type": "flag"},
    "verbosity": {"flag": "--verbosity", "default": "", "type": "int"},
}

def _build_cmd(model_path, port, settings):
    cmd = ["/usr/local/bin/llama-server", "--model", model_path,
           "--host", "127.0.0.1", "--port", str(port)]
    for key, schema in SETTINGS_SCHEMA.items():
        val = settings.get(key, schema["default"])
        if not val and val != 0: continue
        val = str(val)
        if schema["type"] == "flag":
            if val.lower() in ("true", "1", "on", "yes"): cmd.append(schema["flag"])
        else: cmd.extend([schema["flag"], val])
    return cmd

# ── RAG ──────────────────────────────────────────────────────
def _get_rag_db(index_id):
    safe = re.sub(r'[^a-zA-Z0-9_-]', '', index_id)
    db_path = os.path.join(RAG_DIR, safe + ".db")
    idx_path = os.path.join(RAG_DIR, safe + ".faiss")
    db = sqlite3.connect(db_path)
    db.execute("CREATE TABLE IF NOT EXISTS chunks (id INTEGER PRIMARY KEY, text TEXT, timestamp REAL)")
    db.commit()
    if os.path.isfile(idx_path):
        index = faiss.read_index(idx_path)
    else:
        index = faiss.IndexIDMap(faiss.IndexFlatIP(EMBED_DIM))
    return db, index, idx_path

def _get_embedding_slot():
    for alias, s in _slots.items():
        if alias == "embedding" and s["status"] == "ready" and s.get("type") == "local":
            return s
    for s in _slots.values():
        if s["status"] == "ready" and s.get("type") == "local":
            return s
    return None

def get_embedding(text):
    slot = _get_embedding_slot()
    if not slot: return None
    try:
        req = Request(f"http://127.0.0.1:{slot['port']}/v1/embeddings",
                      data=json.dumps({"input": text}).encode(),
                      headers={"Content-Type": "application/json"}, method="POST")
        resp = urlopen(req, timeout=30)
        data = json.loads(resp.read())
        emb = data["data"][0]["embedding"]
        global EMBED_DIM
        if len(emb) != EMBED_DIM: EMBED_DIM = len(emb)
        return emb
    except Exception as e:
        print(f"[RAG] Embedding failed: {e}", flush=True)
        return None

def _split_long_text(text, max_tokens):
    if count_tokens(text) <= max_tokens: return [text]
    parts = text.split("\n\n")
    chunks, current = [], ""
    for part in parts:
        if count_tokens(current + "\n\n" + part) > max_tokens and current:
            chunks.append(current)
            current = part
        else:
            current = (current + "\n\n" + part).strip()
    if current: chunks.append(current)
    return chunks if chunks else [text[:max_tokens * 4]]

def chunk_messages(messages):
    chunks, current, current_tokens = [], [], 0
    for m in messages:
        text = m.get("role", "user") + ": " + m.get("content", "")
        msg_tokens = count_tokens(text)
        if msg_tokens > CHUNK_SIZE:
            if current:
                chunks.append("\n".join(current))
                current, current_tokens = [], 0
            for sub in _split_long_text(text, CHUNK_SIZE):
                chunks.append(sub)
            continue
        if current_tokens + msg_tokens > CHUNK_SIZE and current:
            chunks.append("\n".join(current))
            overlap_msgs, overlap_tokens = [], 0
            for prev in reversed(current):
                t = count_tokens(prev)
                if overlap_tokens + t > CHUNK_OVERLAP: break
                overlap_msgs.insert(0, prev)
                overlap_tokens += t
            current, current_tokens = overlap_msgs, overlap_tokens
        current.append(text)
        current_tokens += msg_tokens
    if current: chunks.append("\n".join(current))
    return chunks

def rag_archive(index_id, messages):
    if not messages: return 0
    chunks = chunk_messages(messages)
    db, index, idx_path = _get_rag_db(index_id)
    archived = 0
    for chunk_text in chunks:
        vec = get_embedding(chunk_text)
        if vec is None: continue
        vec_np = np.array([vec], dtype=np.float32)
        faiss.normalize_L2(vec_np)
        db.execute("INSERT INTO chunks (text, timestamp) VALUES (?, ?)", (chunk_text, time.time()))
        sqlite_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        index.add_with_ids(vec_np, np.array([sqlite_id], dtype=np.int64))
        archived += 1
    db.commit()
    db.close()
    tmp = idx_path + ".tmp"
    faiss.write_index(index, tmp)
    os.replace(tmp, idx_path)
    print(f"[RAG] Archived {archived} chunks for {index_id}", flush=True)
    return archived

def rag_search(index_id, query, top_k=3):
    idx_path = os.path.join(RAG_DIR, re.sub(r'[^a-zA-Z0-9_-]', '', index_id) + ".faiss")
    if not os.path.isfile(idx_path): return []
    vec = get_embedding(query)
    if vec is None: return []
    db, index, idx_path = _get_rag_db(index_id)
    if index.ntotal == 0:
        db.close()
        return []
    vec_np = np.array([vec], dtype=np.float32)
    faiss.normalize_L2(vec_np)
    k = min(top_k, index.ntotal)
    scores, ids = index.search(vec_np, k)
    results = []
    for i, sid in enumerate(ids[0]):
        if sid < 0: continue
        row = db.execute("SELECT text FROM chunks WHERE id = ?", (int(sid),)).fetchone()
        if row: results.append({"text": row[0], "score": float(scores[0][i])})
    db.close()
    return results

def rag_clear(index_id):
    safe = re.sub(r'[^a-zA-Z0-9_-]', '', index_id)
    for ext in [".db", ".faiss", ".faiss.tmp"]:
        p = os.path.join(RAG_DIR, safe + ext)
        if os.path.isfile(p): os.remove(p)

def rag_status(index_id):
    safe = re.sub(r'[^a-zA-Z0-9_-]', '', index_id)
    idx_path = os.path.join(RAG_DIR, safe + ".faiss")
    if not os.path.isfile(idx_path): return {"chunks": 0}
    try:
        idx = faiss.read_index(idx_path)
        return {"chunks": idx.ntotal}
    except: return {"chunks": 0}

# ── Slot Management ──────────────────────────────────────────
def load_model(model_file, alias=None, settings=None, system_prompt="", rag_enabled=True, rag_top_k=3):
    if not os.path.isfile(os.path.join(MODEL_DIR, model_file)):
        return False, None, f"Model not found: {model_file}"
    if alias is None: alias = _auto_name(model_file)
    if settings is None: settings = {}
    if "gpu_layers" not in settings: settings["gpu_layers"] = GPU_LAYERS
    if "ctx_size" not in settings: settings["ctx_size"] = CTX_SIZE

    with _slots_lock:
        if alias in _slots: return False, alias, f"Alias '{alias}' already in use"
        for a, s in _slots.items():
            if s.get("model_file") == model_file and s.get("type") == "local":
                return False, a, f"Model already loaded as '{a}'"

    port = _get_free_port()
    model_path = os.path.join(MODEL_DIR, model_file)
    file_size = os.path.getsize(model_path)

    slot = {
        "type": "local", "model_file": model_file, "alias": alias, "port": port,
        "process": None, "status": "loading", "detail": f"Loading {model_file}...",
        "vram_est_mb": int(file_size / 1024 / 1024 * 1.2),
        "system_prompt": system_prompt, "rag_enabled": rag_enabled, "rag_top_k": rag_top_k,
        "settings": settings, "loaded_at": None,
    }
    with _slots_lock: _slots[alias] = slot

    cmd = _build_cmd(model_path, port, settings)
    print(f"[ROUTER] Loading {model_file} as '{alias}' on port {port}", flush=True)
    try:
        proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
        slot["process"] = proc
    except Exception as e:
        slot["status"] = "error"
        slot["detail"] = f"Failed to start: {e}"
        return False, alias, str(e)

    def _wait_ready():
        for i in range(300):
            time.sleep(0.5)
            slot["detail"] = f"Loading {model_file}... ({i//2}s)"
            try:
                r = urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
                if r.status == 200:
                    slot["status"] = "ready"
                    slot["detail"] = f"{alias} ready"
                    slot["loaded_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    print(f"[ROUTER] '{alias}' ready on port {port}", flush=True)
                    _save_config()
                    return
            except: pass
            if proc.poll() is not None:
                slot["status"] = "error"
                slot["detail"] = f"Crashed (exit {proc.returncode})"
                print(f"[ROUTER] '{alias}' exited with code {proc.returncode}", flush=True)
                return
        slot["status"] = "ready"
        slot["detail"] = f"{alias} (slow start)"
        slot["loaded_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        _save_config()
    threading.Thread(target=_wait_ready, daemon=True).start()
    return True, alias, f"Loading {model_file} as '{alias}'"

def add_remote_provider(alias, provider_type, api_base, api_key, remote_model,
                         system_prompt="", settings=None, rag_enabled=False, rag_top_k=3):
    if not alias or not provider_type or not api_base or not remote_model:
        return False, "Missing required fields"
    with _slots_lock:
        if alias in _slots: return False, f"Alias '{alias}' already in use"
    slot = {
        "type": provider_type, "alias": alias, "api_base": api_base.rstrip("/"),
        "api_key": api_key, "remote_model": remote_model,
        "system_prompt": system_prompt, "rag_enabled": rag_enabled, "rag_top_k": rag_top_k,
        "settings": settings or {}, "status": "ready", "loaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    with _slots_lock: _slots[alias] = slot
    _save_config()
    _save_providers()
    print(f"[ROUTER] Added remote provider '{alias}' ({provider_type}: {remote_model})", flush=True)
    return True, f"Added '{alias}'"

def unload_model(alias):
    with _slots_lock:
        if alias not in _slots: return False, f"No agent loaded as '{alias}'"
        slot = _slots[alias]
        if slot.get("type") == "local":
            proc = slot.get("process")
            if proc and proc.poll() is None:
                print(f"[ROUTER] Unloading '{alias}' (pid {proc.pid})", flush=True)
                proc.terminate()
                try: proc.wait(timeout=10)
                except: proc.kill()
        del _slots[alias]
    _save_config()
    print(f"[ROUTER] '{alias}' unloaded", flush=True)
    return True, f"Unloaded '{alias}'"

def _resolve_model(model_name):
    if not model_name or model_name == "default":
        for s in _slots.values():
            if s["status"] == "ready" and s.get("type") == "local":
                return s, None
        for s in _slots.values():
            if s["status"] == "ready":
                return s, None
        return None, "No agents loaded"
    if model_name in _slots:
        s = _slots[model_name]
        if s["status"] == "ready": return s, None
        return None, f"Agent '{model_name}' is {s['status']}: {s.get('detail', '')}"
    for s in _slots.values():
        if s.get("model_file") == model_name and s["status"] == "ready": return s, None
    for alias, s in _slots.items():
        if model_name.lower() in alias.lower() and s["status"] == "ready": return s, None
    return None, f"Agent '{model_name}' not found. Available: {', '.join(_slots.keys()) or 'none'}"

# ── Agent Request Pipeline ───────────────────────────────────
def _apply_agent_pipeline(slot, messages, request_settings=None):
    # 1. System prompt: concatenate slot identity + incoming task context
    slot_prompt = slot.get("system_prompt", "")
    incoming_sys = None
    if messages and messages[0].get("role") == "system":
        incoming_sys = messages.pop(0)

    if slot_prompt and incoming_sys:
        combined = slot_prompt + "\n\n" + incoming_sys["content"]
        messages.insert(0, {"role": "system", "content": combined})
    elif slot_prompt:
        messages.insert(0, {"role": "system", "content": slot_prompt})
    elif incoming_sys:
        messages.insert(0, incoming_sys)

    # 2. Context trimming + auto-archive
    trimmed = []
    ctx_size = int(slot.get("settings", {}).get("ctx_size", 4096))
    messages, trimmed, _, _ = trim_messages(messages, ctx_size)
    if trimmed and slot.get("rag_enabled", False):
        index_id = slot.get("alias", "default")
        try:
            rag_archive(index_id, trimmed)
        except Exception as e:
            print(f"[RAG] Auto-archive error: {e}", flush=True)

    # 3. RAG: search for relevant context and inject
    rag_results = []
    if slot.get("rag_enabled", False):
        index_id = slot.get("alias", "default")
        user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_msg = m.get("content", "")
                break
        if user_msg:
            try:
                top_k = slot.get("rag_top_k", 3)
                rag_results = rag_search(index_id, user_msg, top_k=top_k)
            except Exception as e:
                print(f"[RAG] Search error: {e}", flush=True)
        if rag_results:
            rag_text = "\n---\n".join([r["text"] for r in rag_results])
            rag_note = {"role": "system", "content": "[Earlier context:]\n" + rag_text}
            if messages and messages[0].get("role") == "system":
                messages.insert(1, rag_note)
            else:
                messages.insert(0, rag_note)

    # 3. Merge settings: request overrides slot defaults
    merged = dict(slot.get("settings", {}))
    if request_settings:
        for k, v in request_settings.items():
            if v is not None and str(v) != "":
                merged[k] = v

    return messages, merged, rag_results, trimmed

def _proxy_local(slot, messages, settings):
    payload = {"model": slot["alias"], "messages": messages, "stream": False}
    for key in ["temperature", "top_p", "top_k", "min_p", "repeat_penalty", "max_tokens", "seed"]:
        if key in settings and settings[key] is not None and str(settings[key]) != "":
            payload[key] = settings[key]
    if "max_tokens" not in payload: payload["max_tokens"] = 1024
    data = json.dumps(payload).encode()
    req = Request(f"http://127.0.0.1:{slot['port']}/v1/chat/completions",
                  data=data, headers={"Content-Type": "application/json"}, method="POST")
    resp = urlopen(req, timeout=300)
    return json.loads(resp.read())

def _proxy_openai(slot, messages, settings):
    payload = {"model": slot["remote_model"], "messages": messages, "stream": False}
    for key in ["temperature", "top_p", "max_tokens", "seed"]:
        if key in settings and settings[key] is not None and str(settings[key]) != "":
            payload[key] = settings[key]
    if "max_tokens" not in payload: payload["max_tokens"] = 1024
    data = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {slot.get('api_key', '')}"}
    req = Request(f"{slot['api_base']}/chat/completions", data=data, headers=headers, method="POST")
    resp = urlopen(req, timeout=300)
    return json.loads(resp.read())

def _proxy_anthropic(slot, messages, settings):
    # Translate OpenAI format -> Anthropic Messages API
    sys_text = ""
    api_msgs = []
    for m in messages:
        if m["role"] == "system":
            sys_text = (sys_text + "\n" + m["content"]).strip()
        else:
            api_msgs.append({"role": m["role"], "content": m["content"]})
    payload = {"model": slot["remote_model"], "messages": api_msgs, "max_tokens": int(settings.get("max_tokens", 1024))}
    if sys_text: payload["system"] = sys_text
    if "temperature" in settings: payload["temperature"] = float(settings["temperature"])
    data = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json",
               "x-api-key": slot.get("api_key", ""),
               "anthropic-version": "2023-06-01"}
    req = Request(f"{slot['api_base']}/messages", data=data, headers=headers, method="POST")
    resp = urlopen(req, timeout=300)
    result = json.loads(resp.read())
    # Translate back to OpenAI format
    content = ""
    for block in result.get("content", []):
        if block.get("type") == "text": content += block["text"]
    return {"choices": [{"message": {"role": "assistant", "content": content}}],
            "usage": result.get("usage", {})}

def _proxy_google(slot, messages, settings):
    # Translate OpenAI format -> Gemini generateContent
    sys_text = ""
    contents = []
    for m in messages:
        if m["role"] == "system":
            sys_text = (sys_text + "\n" + m["content"]).strip()
        else:
            role = "user" if m["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
    payload = {"contents": contents}
    if sys_text:
        payload["system_instruction"] = {"parts": [{"text": sys_text}]}
    gc = {}
    if "temperature" in settings: gc["temperature"] = float(settings["temperature"])
    if "max_tokens" in settings: gc["maxOutputTokens"] = int(settings["max_tokens"])
    if gc: payload["generationConfig"] = gc
    data = json.dumps(payload).encode()
    model = slot["remote_model"]
    url = f"{slot['api_base']}/v1beta/models/{model}:generateContent?key={slot.get('api_key', '')}"
    req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    resp = urlopen(req, timeout=300)
    result = json.loads(resp.read())
    content = ""
    for candidate in result.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            content += part.get("text", "")
    return {"choices": [{"message": {"role": "assistant", "content": content}}], "usage": {}}

def route_chat(slot, messages, request_settings=None):
    messages = [dict(m) for m in messages]
    messages, merged, rag_results, trimmed = _apply_agent_pipeline(slot, messages, request_settings)
    ptype = slot.get("type", "local")
    if ptype == "local": result = _proxy_local(slot, messages, merged)
    elif ptype == "openai" or ptype == "custom": result = _proxy_openai(slot, messages, merged)
    elif ptype == "anthropic": result = _proxy_anthropic(slot, messages, merged)
    elif ptype == "google": result = _proxy_google(slot, messages, merged)
    else: raise ValueError(f"Unknown provider type: {ptype}")
    result["_rag"] = {"chunks_used": len(rag_results), "trimmed": len(trimmed), "archived": len(trimmed) if trimmed and slot.get("rag_enabled") else 0}
    return result

# ── Config Persistence ───────────────────────────────────────
def _save_config():
    try:
        cfg = {"agents": []}
        for alias, s in _slots.items():
            entry = {"alias": s["alias"], "type": s.get("type", "local"),
                     "system_prompt": s.get("system_prompt", ""),
                     "rag_enabled": s.get("rag_enabled", False),
                     "rag_top_k": s.get("rag_top_k", 3),
                     "settings": s.get("settings", {})}
            if s.get("type") == "local":
                entry["model_file"] = s.get("model_file", "")
            else:
                entry["remote_model"] = s.get("remote_model", "")
                entry["provider_type"] = s.get("type", "openai")
                entry["api_base"] = s.get("api_base", "")
            if s["status"] in ("ready", "loading"):
                cfg["agents"].append(entry)
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w") as f: json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"[ROUTER] Config save failed: {e}", flush=True)

def _save_providers():
    try:
        keys = {}
        for alias, s in _slots.items():
            if s.get("api_key"):
                keys[alias] = s["api_key"]
        with open(PROVIDERS_FILE, "w") as f: json.dump(keys, f)
        os.chmod(PROVIDERS_FILE, 0o600)
    except Exception as e:
        print(f"[ROUTER] Provider save failed: {e}", flush=True)

def _load_config():
    try:
        if os.path.isfile(CONFIG_FILE):
            with open(CONFIG_FILE) as f: return json.load(f)
    except: pass
    return None

def _load_provider_keys():
    try:
        if os.path.isfile(PROVIDERS_FILE):
            with open(PROVIDERS_FILE) as f: return json.load(f)
    except: pass
    return {}

# ── Zombie Cleanup ───────────────────────────────────────────
def _kill_all_slots():
    print("[ROUTER] Cleaning up all model processes...", flush=True)
    with _slots_lock:
        for alias, slot in _slots.items():
            proc = slot.get("process")
            if proc and proc.poll() is None:
                print(f"[ROUTER] Killing '{alias}' (pid {proc.pid})", flush=True)
                proc.kill()
atexit.register(_kill_all_slots)

# ── HTTP Handler ─────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_GET(self):
        if self.path == '/api/status':
            slots_info = {}
            for alias, s in _slots.items():
                info = {"type": s.get("type", "local"), "status": s["status"],
                        "detail": s.get("detail", ""), "settings": s.get("settings", {}),
                        "system_prompt": s.get("system_prompt", "")[:100],
                        "rag_enabled": s.get("rag_enabled", False),
                        "rag_top_k": s.get("rag_top_k", 3),
                        "loaded_at": s.get("loaded_at")}
                if s.get("type") == "local":
                    info.update({"model_file": s.get("model_file", ""), "port": s.get("port"),
                                 "vram_est_mb": s.get("vram_est_mb", 0)})
                else:
                    info.update({"remote_model": s.get("remote_model", ""),
                                 "provider_type": s.get("type", "openai")})
                slots_info[alias] = info
            ready = sum(1 for s in _slots.values() if s["status"] == "ready")
            loading = sum(1 for s in _slots.values() if s["status"] == "loading")
            self._json(200, {"status": "ready" if ready > 0 else ("loading" if loading > 0 else "idle"),
                             "detail": f"{ready} agent(s) ready, {loading} loading", "slots": slots_info})

        elif self.path == '/api/models':
            self._json(200, {"models": list_models(),
                             "loaded": {a: {"model_file": s.get("model_file", ""), "type": s.get("type"),
                                            "settings": s.get("settings", {})} for a, s in _slots.items()}})

        elif self.path == '/api/slots':
            self._json(200, {"slots": [
                {"alias": a, "type": s.get("type", "local"), "status": s["status"],
                 "system_prompt": s.get("system_prompt", "")[:100],
                 "rag_enabled": s.get("rag_enabled"), "rag_top_k": s.get("rag_top_k", 3)}
                for a, s in _slots.items()]})

        elif self.path == '/api/vram':
            self._json(200, get_vram_info())

        elif self.path == '/api/settings-schema':
            self._json(200, SETTINGS_SCHEMA)

        elif self.path == '/health':
            ready = any(s["status"] == "ready" for s in _slots.values())
            self._json(200 if ready or not _slots else 503,
                       {"status": "ok" if ready else ("loading" if _slots else "no agents loaded")})

        elif self.path == '/v1/models':
            data = [{"id": a, "object": "model", "owned_by": s.get("type", "local")}
                    for a, s in _slots.items() if s["status"] == "ready"]
            self._json(200, {"object": "list", "data": data})

        elif self.path.startswith('/api/rag/'):
            parts = self.path.split('/')
            if len(parts) >= 5:
                index_id = parts[3]
                action = parts[4]
                if action == 'status':
                    self._json(200, rag_status(index_id))
                else:
                    self._json(404, {"error": "Unknown RAG action"})
            else:
                self._json(400, {"error": "Invalid RAG path"})

        elif self.path.startswith('/v1/'):
            slot, err = _resolve_model("default")
            if slot:
                self._proxy_to_local(slot)
            else:
                self._json(503, {"error": {"message": err, "type": "server_error"}})

        elif self.path == '/' or self.path == '/index.html':
            self._serve_file(os.path.join(PUBLIC_DIR, 'index.html'), 'text/html')
        else:
            safe = self.path.lstrip('/')
            fpath = os.path.join(PUBLIC_DIR, safe)
            if os.path.isfile(fpath):
                ct = 'text/html'
                if fpath.endswith('.js'): ct = 'application/javascript'
                elif fpath.endswith('.css'): ct = 'text/css'
                elif fpath.endswith('.json'): ct = 'application/json'
                self._serve_file(fpath, ct)
            else:
                self.send_response(404)
                self.end_headers()

    def _proxy_to_local(self, slot):
        url = f"http://127.0.0.1:{slot['port']}{self.path}"
        headers = {}
        for key in ['content-type', 'accept', 'authorization']:
            val = self.headers.get(key)
            if val: headers[key] = val
        try:
            req = Request(url, headers=headers, method="GET")
            resp = urlopen(req, timeout=300)
            data = resp.read()
            self.send_response(resp.status)
            self.send_header('Content-Type', resp.headers.get('Content-Type', 'application/json'))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(data)
        except URLError as e:
            self._json(502, {"error": {"message": f"Backend unavailable: {e}"}})

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length) if length else b''

        if self.path == '/api/slots/load':
            try:
                d = json.loads(body)
                ok, alias_out, detail = load_model(
                    d.get('model', ''), d.get('alias'), d.get('settings'),
                    d.get('system_prompt', ''), d.get('rag_enabled', True), d.get('rag_top_k', 3))
                self._json(200 if ok else 400, {"ok": ok, "alias": alias_out, "detail": detail})
            except Exception as e:
                self._json(500, {"error": str(e)})

        elif self.path == '/api/providers/add':
            try:
                d = json.loads(body)
                ok, detail = add_remote_provider(
                    d.get('alias', ''), d.get('type', 'openai'), d.get('api_base', ''),
                    d.get('api_key', ''), d.get('remote_model', ''),
                    d.get('system_prompt', ''), d.get('settings'), d.get('rag_enabled', False),
                    d.get('rag_top_k', 3))
                self._json(200 if ok else 400, {"ok": ok, "detail": detail})
            except Exception as e:
                self._json(500, {"error": str(e)})

        elif self.path == '/api/slots/unload':
            try:
                d = json.loads(body)
                ok, detail = unload_model(d.get('alias', ''))
                self._json(200 if ok else 400, {"ok": ok, "detail": detail})
            except Exception as e:
                self._json(500, {"error": str(e)})

        elif self.path == '/api/slots/update':
            try:
                d = json.loads(body)
                alias = d.get('alias', '')
                if alias not in _slots:
                    self._json(404, {"error": f"Agent '{alias}' not found"})
                    return
                slot = _slots[alias]
                for key in ['system_prompt', 'rag_enabled', 'rag_top_k']:
                    if key in d: slot[key] = d[key]
                if 'settings' in d:
                    for k, v in d['settings'].items():
                        slot['settings'][k] = v
                _save_config()
                self._json(200, {"ok": True})
            except Exception as e:
                self._json(500, {"error": str(e)})

        elif self.path.startswith('/api/rag/'):
            parts = self.path.split('/')
            if len(parts) >= 5:
                index_id = parts[3]
                action = parts[4]
                if action == 'clear':
                    rag_clear(index_id)
                    self._json(200, {"ok": True})
                elif action == 'archive':
                    try:
                        d = json.loads(body)
                        msgs = d.get('messages', [])
                        n = rag_archive(index_id, msgs)
                        self._json(200, {"ok": True, "archived": n})
                    except Exception as e:
                        self._json(500, {"error": str(e)})
                elif action == 'search':
                    try:
                        d = json.loads(body)
                        results = rag_search(index_id, d.get('query', ''), d.get('top_k', 3))
                        self._json(200, {"results": results})
                    except Exception as e:
                        self._json(500, {"error": str(e)})
                else:
                    self._json(404, {"error": "Unknown RAG action"})
            else:
                self._json(400, {"error": "Invalid RAG path"})

        elif self.path == '/v1/embeddings':
            try:
                d = json.loads(body) if body else {}
                model_name = d.get("model", "embedding")
            except: model_name = "embedding"
            slot, err = _resolve_model(model_name)
            if not slot: slot, err = _resolve_model("default")
            if slot and slot.get("type") == "local":
                url = f"http://127.0.0.1:{slot['port']}/v1/embeddings"
                try:
                    req = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
                    resp = urlopen(req, timeout=30)
                    data = resp.read()
                    self.send_response(resp.status)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(data)
                except URLError as e:
                    self._json(502, {"error": {"message": f"Embedding unavailable: {e}"}})
            else:
                self._json(503, {"error": {"message": "No local model for embeddings"}})

        elif self.path == '/v1/chat/completions':
            try:
                d = json.loads(body) if body else {}
                model_name = d.get("model", "default")
                messages = d.get("messages", [])
                req_settings = {}
                for key in ["temperature", "top_p", "top_k", "min_p", "repeat_penalty", "max_tokens", "seed"]:
                    if key in d: req_settings[key] = d[key]
            except Exception as e:
                self._json(400, {"error": {"message": str(e)}})
                return
            slot, err = _resolve_model(model_name)
            if not slot:
                self._json(503, {"error": {"message": err, "type": "server_error"}})
                return
            try:
                result = route_chat(slot, messages, req_settings)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                self._json(502, {"error": {"message": str(e), "type": "server_error"}})

        elif self.path.startswith('/v1/'):
            try:
                d = json.loads(body) if body else {}
                model_name = d.get("model", "default")
            except: model_name = "default"
            slot, err = _resolve_model(model_name)
            if slot and slot.get("type") == "local":
                url = f"http://127.0.0.1:{slot['port']}{self.path}"
                try:
                    req = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
                    resp = urlopen(req, timeout=300)
                    data = resp.read()
                    self.send_response(resp.status)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(data)
                except URLError as e:
                    self._json(502, {"error": {"message": f"Backend unavailable: {e}"}})
            else:
                self._json(503, {"error": {"message": err or "No local model", "type": "server_error"}})

        else:
            self._json(404, {"error": "Not found"})

    def _json(self, code, data):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        try: self.wfile.write(json.dumps(data).encode())
        except BrokenPipeError: pass

    def _serve_file(self, path, content_type):
        try:
            with open(path, 'rb') as f: data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()

# ── Main ─────────────────────────────────────────────────────
def main():
    server = ThreadingHTTPServer(("0.0.0.0", LISTEN_PORT), Handler)
    print(f"[ROUTER] Model Router v3.0 listening on port {LISTEN_PORT}", flush=True)

    def _auto_load():
        cfg = _load_config()
        keys = _load_provider_keys()
        if cfg and cfg.get("agents"):
            print(f"[ROUTER] Restoring {len(cfg['agents'])} agent(s) from config", flush=True)
            for entry in cfg["agents"]:
                if entry.get("type", "local") == "local":
                    mf = entry.get("model_file", "")
                    if mf and os.path.isfile(os.path.join(MODEL_DIR, mf)):
                        load_model(mf, entry.get("alias"), entry.get("settings"),
                                   entry.get("system_prompt", ""), entry.get("rag_enabled", True),
                                   entry.get("rag_top_k", 3))
                        time.sleep(2)
                else:
                    alias = entry.get("alias", "")
                    key = keys.get(alias, "")
                    add_remote_provider(alias, entry.get("provider_type", "openai"),
                                        entry.get("api_base", ""), key,
                                        entry.get("remote_model", ""),
                                        entry.get("system_prompt", ""),
                                        entry.get("settings"), entry.get("rag_enabled", False),
                                        entry.get("rag_top_k", 3))
        else:
            models = list_models()
            if models:
                smallest = min(models, key=lambda m: m["bytes"])
                print(f"[ROUTER] First run - loading: {smallest['name']}", flush=True)
                load_model(smallest["name"])
                time.sleep(2)
                embed = [m for m in models if "minilm" in m["name"].lower() or "embed" in m["name"].lower()]
                if embed and embed[0]["name"] != smallest["name"]:
                    print(f"[ROUTER] Loading embedding: {embed[0]['name']}", flush=True)
                    load_model(embed[0]["name"], alias="embedding", settings={"gpu_layers": "0", "ctx_size": "512"})
            else:
                print(f"[ROUTER] No models in {MODEL_DIR}", flush=True)
    threading.Thread(target=_auto_load, daemon=True).start()

    def shutdown(sig, frame):
        print("[ROUTER] Shutting down...", flush=True)
        _kill_all_slots()
        server.shutdown()
        sys.exit(0)
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    server.serve_forever()

if __name__ == "__main__":
    main()
