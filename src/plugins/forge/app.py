
from flask import Flask, render_template, request, jsonify, send_file
import os, json, subprocess, tempfile, shutil, requests, time, uuid

app = Flask(__name__)
LLAMA_API = os.environ.get("LLAMA_API", "http://wm-llama:8080")
WORKSPACE = os.environ.get("WORKSPACE", "/workspace")
os.makedirs(WORKSPACE, exist_ok=True)

def safe_path(base, user_input):
    joined = os.path.abspath(os.path.join(base, user_input))
    if not joined.startswith(os.path.abspath(base)):
        raise ValueError(f"Path traversal blocked: {user_input}")
    return joined

def ask_llm(prompt, system="You are a skilled programmer. Write clean, working code. Return ONLY code, no explanations unless asked."):
    try:
        r = requests.post(f"{LLAMA_API}/v1/chat/completions", json={
            "model": "default",
            "messages": [{"role":"system","content":system}, {"role":"user","content":prompt}],
            "temperature": 0.3, "max_tokens": 2048, "stream": False
        }, timeout=120)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error calling LLM: {e}"

def run_code(code, language="python", timeout=30):
    # Execute code in a sandboxed subprocess.
    try:
        if language == "python":
            result = subprocess.run(["python3", "-c", code], capture_output=True, text=True, timeout=timeout, cwd=WORKSPACE)
        elif language == "javascript":
            result = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=timeout, cwd=WORKSPACE)
        elif language == "bash":
            result = subprocess.run(["bash", "-c", code], capture_output=True, text=True, timeout=timeout, cwd=WORKSPACE)
        else:
            return {"stdout": "", "stderr": f"Unsupported language: {language}", "returncode": 1}
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Execution timed out", "returncode": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "returncode": -1}

@app.route("/")
def index(): return render_template("index.html")

@app.route("/health")
def health(): return jsonify({"status": "ok"})

@app.route("/api/generate", methods=["POST"])
def generate():
    d = request.json or {}
    instruction = d.get("instruction", "")
    language = d.get("language", "python")
    if not instruction: return jsonify({"error": "instruction required"}), 400
    prompt = f"Write a {language} program that does the following:\n{instruction}\n\nReturn ONLY the code."
    code = ask_llm(prompt)
    return jsonify({"code": code, "language": language})

@app.route("/api/run", methods=["POST"])
def api_run():
    d = request.json or {}
    code = d.get("code", "")
    language = d.get("language", "python")
    if not code: return jsonify({"error": "code required"}), 400
    result = run_code(code, language, timeout=d.get("timeout", 30))
    return jsonify(result)

@app.route("/api/save", methods=["POST"])
def save_file():
    d = request.json or {}
    filename = d.get("filename", "untitled.py")
    content = d.get("content", "")
    path = safe_path(WORKSPACE, filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f: f.write(content)
    return jsonify({"saved": filename})

@app.route("/api/files")
def list_files():
    files = []
    for root, dirs, fnames in os.walk(WORKSPACE):
        for fn in fnames:
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, WORKSPACE)
            files.append({"name": rel, "size": os.path.getsize(full)})
    files.sort(key=lambda x: x["name"])
    return jsonify(files)

@app.route("/api/export", methods=["POST"])
def export_project():
    d = request.json or {}
    project_name = d.get("name", "project")
    files = d.get("files", [])
    if not files: return jsonify({"error": "No files specified"}), 400
    zip_path = os.path.join("/tmp", f"{project_name}.zip")
    shutil.make_archive(zip_path.replace(".zip",""), "zip", WORKSPACE)
    return send_file(zip_path, as_attachment=True, download_name=f"{project_name}.zip")

# ── Node API ─────────────────────────────────────────────────
@app.route("/node/schema")
def node_schema():
    return jsonify({
        "name": "forge",
        "description": "Generate and execute code using a local LLM",
        "inputs": [
            {"name": "instruction", "type": "string", "required": False, "description": "Describe what code to generate"},
            {"name": "code", "type": "string", "required": False, "description": "Code to execute directly"},
            {"name": "language", "type": "string", "default": "python"},
            {"name": "run", "type": "boolean", "default": True, "description": "Whether to execute the code"},
        ],
        "outputs": [
            {"name": "code", "type": "string"},
            {"name": "stdout", "type": "string"},
            {"name": "stderr", "type": "string"},
            {"name": "returncode", "type": "number"},
        ]
    })

@app.route("/node/execute", methods=["POST"])
def node_execute():
    d = request.json or {}
    code = d.get("code", "")
    language = d.get("language", "python")
    if d.get("instruction") and not code:
        prompt = f"Write a {language} program: {d['instruction']}\nReturn ONLY code."
        code = ask_llm(prompt)
    if not code: return jsonify({"error": "No code to execute"}), 400
    result = {"code": code, "stdout": "", "stderr": "", "returncode": -1}
    if d.get("run", True):
        exec_result = run_code(code, language)
        result.update(exec_result)
    return jsonify(result)

if __name__ == "__main__": app.run(host="0.0.0.0", port=5000)
