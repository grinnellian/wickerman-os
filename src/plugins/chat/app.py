from flask import Flask, render_template, request, jsonify
import os, json, requests, uuid, time, glob

app = Flask(__name__)
LLAMA_API = os.environ.get("LLAMA_API", "http://wm-llama:8080")
DATA_DIR = "/data"
CONV_DIR = os.path.join(DATA_DIR, "conversations")
os.makedirs(CONV_DIR, exist_ok=True)

def _conv_path(cid):
    if not cid.isalnum(): raise ValueError("Invalid Conversation ID")
    return os.path.join(CONV_DIR, cid + ".json")

def save_conversation(conv):
    target = _conv_path(conv["id"])
    tmp = target + ".tmp"
    with open(tmp, "w") as f: json.dump(conv, f)
    os.replace(tmp, target)

def load_conversation(cid):
    p = _conv_path(cid)
    if os.path.isfile(p):
        with open(p) as f: return json.load(f)
    return None

def list_conversations():
    convs = []
    for p in glob.glob(os.path.join(CONV_DIR, "*.json")):
        try:
            with open(p) as f: c = json.load(f)
            convs.append({"id": c["id"], "title": c.get("title","Untitled"), "agent": c.get("agent","default"), "created": c.get("created",0), "message_count": len(c.get("messages",[]))})
        except: pass
    convs.sort(key=lambda c: c.get("created",0), reverse=True)
    return convs

def delete_conversation(cid):
    p = _conv_path(cid)
    if os.path.isfile(p):
        os.remove(p)
        return True
    return False

@app.route("/")
def index(): return render_template("index.html")

@app.route("/health")
def health(): return jsonify({"status": "ok"})

@app.route("/api/agents")
def api_agents():
    try:
        r = requests.get(LLAMA_API + "/v1/models", timeout=5)
        return jsonify(r.json())
    except: return jsonify({"data": []})

@app.route("/api/conversations", methods=["GET"])
def api_list_convs(): return jsonify({"conversations": list_conversations()})

@app.route("/api/conversations", methods=["POST"])
def api_create_conv():
    d = request.json or {}
    cid = str(uuid.uuid4())[:8]
    conv = {"id": cid, "title": d.get("title", "New Chat"), "agent": d.get("agent", "default"), "messages": [], "created": time.time()}
    save_conversation(conv)
    return jsonify(conv)

@app.route("/api/conversations/<cid>", methods=["GET"])
def api_get_conv(cid):
    conv = load_conversation(cid)
    if not conv: return jsonify({"error": "Not found"}), 404
    return jsonify(conv)

@app.route("/api/conversations/<cid>", methods=["PUT"])
def api_update_conv(cid):
    conv = load_conversation(cid)
    if not conv: return jsonify({"error": "Not found"}), 404
    d = request.json or {}
    for key in ["title", "agent"]:
        if key in d: conv[key] = d[key]
    save_conversation(conv)
    return jsonify(conv)

@app.route("/api/conversations/<cid>", methods=["DELETE"])
def api_delete_conv(cid):
    if delete_conversation(cid): return jsonify({"ok": True})
    return jsonify({"error": "Not found"}), 404

@app.route("/api/conversations/<cid>/chat", methods=["POST"])
def api_chat(cid):
    conv = load_conversation(cid)
    if not conv: return jsonify({"error": "Not found"}), 404
    d = request.json or {}
    user_msg = d.get("message", "").strip()
    if not user_msg: return jsonify({"error": "Empty message"}), 400
    if conv["title"] == "New Chat" and len(conv["messages"]) == 0:
        conv["title"] = user_msg[:50] + ("..." if len(user_msg) > 50 else "")
    api_msgs = list(conv["messages"]) + [{"role": "user", "content": user_msg}]
    try:
        payload = {"model": conv.get("agent", "default"), "messages": api_msgs, "stream": False}
        r = requests.post(LLAMA_API + "/v1/chat/completions", json=payload, timeout=300)
        r.raise_for_status()
        data = r.json()
        reply = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        rag_info = data.get("_rag", {})
        conv["messages"].append({"role": "user", "content": user_msg})
        conv["messages"].append({"role": "assistant", "content": reply})
        save_conversation(conv)
        return jsonify({"response": reply, "usage": usage, "context": {"trimmed": rag_info.get("trimmed", 0), "rag_chunks": rag_info.get("chunks_used", 0), "archived": rag_info.get("archived", 0)}})
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Cannot reach Model Router. Is wm-llama running?"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/conversations/<cid>/context", methods=["GET"])
def api_context_info(cid):
    conv = load_conversation(cid)
    if not conv: return jsonify({"error": "Not found"}), 404
    rag_chunks = 0
    try:
        r = requests.get(LLAMA_API + "/api/rag/" + conv.get("agent", "default") + "/status", timeout=3)
        if r.ok: rag_chunks = r.json().get("chunks", 0)
    except: pass
    return jsonify({"messages": len(conv.get("messages", [])), "rag_chunks": rag_chunks})

@app.route("/api/conversations/<cid>/clear", methods=["POST"])
def api_clear_conv(cid):
    conv = load_conversation(cid)
    if not conv: return jsonify({"error": "Not found"}), 404
    conv["messages"] = []
    save_conversation(conv)
    return jsonify({"ok": True})

@app.route("/node/schema")
def node_schema():
    return jsonify({"name": "chat", "description": "Send a message to a Wickerman agent", "inputs": [{"name": "user_message", "type": "string", "required": True}, {"name": "agent", "type": "string", "required": False, "default": "default"}, {"name": "conversation_history", "type": "array", "required": False}], "outputs": [{"name": "response", "type": "string"}, {"name": "tokens_used", "type": "object"}, {"name": "messages", "type": "array"}]})

@app.route("/node/execute", methods=["POST"])
def node_execute():
    d = request.json or {}
    user_msg = d.get("user_message", "")
    if not user_msg: return jsonify({"error": "user_message is required"}), 400
    history = d.get("conversation_history", [])
    messages = history + [{"role": "user", "content": user_msg}]
    agent = d.get("agent", "default")
    try:
        payload = {"model": agent, "messages": messages, "stream": False}
        r = requests.post(LLAMA_API + "/v1/chat/completions", json=payload, timeout=300)
        r.raise_for_status()
        data = r.json()
        reply = data["choices"][0]["message"]["content"]
        messages.append({"role": "assistant", "content": reply})
        return jsonify({"response": reply, "tokens_used": data.get("usage", {}), "messages": messages})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__": app.run(host="0.0.0.0", port=5000)
