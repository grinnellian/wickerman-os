
from flask import Flask, render_template, request, jsonify
import os, json, requests, threading, time, re
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
MODEL_DIR  = "/data/models"
STATE_FILE = "/data/downloads_state.json"
downloads  = {}
_lock      = threading.Lock()
_dl_pool   = ThreadPoolExecutor(max_workers=3)
os.makedirs(MODEL_DIR, exist_ok=True)

def save_state():
    try:
        with _lock:
            snapshot = json.dumps(downloads)
        with open(STATE_FILE, "w") as f: f.write(snapshot)
    except Exception as e:
        print(f"[WARN] save_state failed: {e}", flush=True)

try:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f: downloads = json.load(f)
        for tid, info in downloads.items():
            if info.get("status") == "downloading": downloads[tid]["status"] = "interrupted"
        save_state()
except Exception: downloads = {}

def human_size(b):
    for u in ["B","KB","MB","GB","TB"]:
        if b < 1024: return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} PB"

def parse_hf_input(text):
    text = text.strip().rstrip("/")
    m = re.match(r'https?://huggingface\.co/([^/]+/[^/]+)', text)
    if m: return m.group(1)
    if "/" in text and not text.startswith("http"): return text
    return None

def download_file(url, dest, task_id, filename):
    try:
        headers = {}; part_file = dest + ".part"; downloaded = 0
        if os.path.exists(part_file):
            downloaded = os.path.getsize(part_file)
            headers["Range"] = f"bytes={downloaded}-"
        r = requests.get(url, stream=True, timeout=60, headers=headers)
        if r.status_code == 416:
            if os.path.exists(part_file): os.rename(part_file, dest)
            with _lock: downloads[task_id]["status"] = "complete"
            save_state(); return
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        if r.status_code == 206: total += downloaded
        else: downloaded = 0
        last_save = time.time()
        mode = "ab" if r.status_code == 206 else "wb"
        with open(part_file, mode) as f:
            for chunk in r.iter_content(chunk_size=1024*256):
                f.write(chunk); downloaded += len(chunk)
                with _lock:
                    downloads[task_id] = {"status":"downloading","total":total,"downloaded":downloaded,"filename":filename,"url":url,"dest":dest}
                now = time.time()
                if now - last_save >= 3: save_state(); last_save = now
        os.rename(part_file, dest)
        with _lock: downloads[task_id]["status"] = "complete"
        save_state()
    except Exception as e:
        with _lock: downloads[task_id] = {"status":"error","error":str(e),"filename":filename,"url":url,"dest":dest}
        save_state()

@app.route("/")
def index(): return render_template("index.html")

@app.route("/api/hf/lookup", methods=["POST"])
def hf_lookup():
    text = (request.json or {}).get("query","").strip()
    repo_id = parse_hf_input(text)
    if not repo_id: return jsonify({"error":"Use format: owner/model or a HuggingFace URL"}), 400
    try:
        info = requests.get(f"https://huggingface.co/api/models/{repo_id}", timeout=15).json()
        if "error" in info: return jsonify({"error":f"Model not found: {repo_id}"}), 404
        tree = requests.get(f"https://huggingface.co/api/models/{repo_id}/tree/main", timeout=15).json()
        files = []
        for item in tree:
            if item.get("type") != "file": continue
            name, size = item.get("path",""), item.get("size",0)
            ext = name.rsplit(".",1)[-1].lower() if "." in name else ""
            cat = "other"
            if ext == "gguf": cat = "gguf"
            elif ext in ("safetensors","bin","pt","pth"): cat = "weights"
            elif ext in ("json","txt","md","yaml","yml"): cat = "config"
            elif "tokenizer" in name.lower(): cat = "tokenizer"
            files.append({"name":name,"size":size,"size_h":human_size(size),"ext":ext,"category":cat,
                "url":f"https://huggingface.co/{repo_id}/resolve/main/{name}"})
        order = {"gguf":0,"quantized":1,"weights":2,"tokenizer":3,"config":4,"other":5}
        files.sort(key=lambda f:(order.get(f["category"],9),f["name"]))
        return jsonify({"repo_id":repo_id,"model_name":info.get("modelId",repo_id),
            "tags":info.get("tags",[])[:20],"files":files,"total_size":human_size(sum(f["size"] for f in files))})
    except requests.exceptions.ConnectionError:
        return jsonify({"error":"Cannot reach HuggingFace."}), 502
    except Exception as e:
        return jsonify({"error":str(e)}), 500

@app.route("/api/download", methods=["POST"])
def start_download():
    data = request.json or {}; url = data.get("url","").strip(); sub = data.get("subfolder","").strip()
    if not url: return jsonify({"error":"No URL"}), 400
    fn = url.rstrip("/").split("/")[-1].split("?")[0]
    if sub: os.makedirs(os.path.join(MODEL_DIR,sub), exist_ok=True); dest = os.path.join(MODEL_DIR,sub,fn)
    else: dest = os.path.join(MODEL_DIR,fn)
    tid = f"{int(time.time())}_{fn}"
    with _lock: downloads[tid] = {"status":"starting","filename":fn,"url":url,"dest":dest}
    threading.Thread(target=download_file,args=(url,dest,tid,fn),daemon=True).start()
    return jsonify({"task_id":tid})

@app.route("/api/download/batch", methods=["POST"])
def batch_download():
    data = request.json or {}; files = data.get("files",[]); sub = data.get("subfolder","").strip()
    tids = []
    for f in files:
        url = f.get("url","").strip()
        if not url: continue
        fn = url.rstrip("/").split("/")[-1].split("?")[0]
        if sub: os.makedirs(os.path.join(MODEL_DIR,sub),exist_ok=True); dest=os.path.join(MODEL_DIR,sub,fn)
        else: dest=os.path.join(MODEL_DIR,fn)
        tid = f"{int(time.time())}_{fn}"
        with _lock: downloads[tid]={"status":"starting","filename":fn,"url":url,"dest":dest}
        _dl_pool.submit(download_file, url, dest, tid, fn)
        tids.append(tid); time.sleep(0.05)
    return jsonify({"task_ids":tids})

@app.route("/api/models")
def list_models():
    result = []
    for root,dirs,files in os.walk(MODEL_DIR):
        for f in files:
            if f.endswith(".part"): continue
            full = os.path.join(root,f); rel = os.path.relpath(full,MODEL_DIR)
            result.append({"name":rel,"size":os.path.getsize(full),"size_h":human_size(os.path.getsize(full))})
    result.sort(key=lambda x:x["name"]); return jsonify(result)

@app.route("/api/status")
def status():
    with _lock: return jsonify(dict(downloads))

@app.route("/api/clear_completed", methods=["POST"])
def clear_completed():
    with _lock:
        rm=[t for t,i in downloads.items() if i.get("status") in ("complete","error","interrupted")]
        for t in rm: del downloads[t]
    save_state(); return jsonify({"cleared":len(rm)})

if __name__ == "__main__": app.run(host="0.0.0.0", port=5000)
