
from flask import Flask, render_template, request, jsonify
import os, json, threading, time, glob

app = Flask(__name__)
MODEL_DIR = os.environ.get("MODEL_DIR", "/models")
DATASET_DIR = os.environ.get("DATASET_DIR", "/datasets")
LORA_DIR = os.environ.get("LORA_DIR", "/loras")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/data/outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LORA_DIR, exist_ok=True)

def safe_path(base, user_input):
    joined = os.path.abspath(os.path.join(base, user_input))
    if not joined.startswith(os.path.abspath(base)):
        raise ValueError(f"Path traversal blocked: {user_input}")
    return joined

training_state = {"status": "idle", "progress": 0, "log": [], "current_job": None}
_lock = threading.Lock()

def log_training(msg):
    with _lock:
        training_state["log"].append(f"[{time.strftime('%H:%M:%S')}] {msg}")
        if len(training_state["log"]) > 500:
            training_state["log"] = training_state["log"][-500:]

def run_training(config):
    try:
        with _lock:
            training_state["status"] = "training"
            training_state["progress"] = 0
            training_state["log"] = []
            training_state["current_job"] = config
        
        log_training(f"Starting training: {config.get('base_model', 'unknown')}")
        log_training(f"Dataset: {config.get('dataset', 'unknown')}")
        
        from unsloth import FastLanguageModel
        from datasets import load_dataset
        from trl import SFTTrainer
        from transformers import TrainingArguments
        
        model_path = safe_path(MODEL_DIR, config["base_model"])
        log_training(f"Loading model: {model_path}")
        
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_path,
            max_seq_length=config.get("max_seq_length", 2048),
            load_in_4bit=config.get("load_in_4bit", True),
        )
        log_training("Model loaded")
        
        model = FastLanguageModel.get_peft_model(
            model, r=config.get("lora_r", 16),
            target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
            lora_alpha=config.get("lora_alpha", 16),
            lora_dropout=0, bias="none", use_gradient_checkpointing="unsloth",
        )
        log_training(f"LoRA applied: r={config.get('lora_r',16)}")
        
        dataset_path = safe_path(DATASET_DIR, config["dataset"])
        ext = dataset_path.rsplit(".",1)[-1].lower()
        if ext == "jsonl": ds = load_dataset("json", data_files=dataset_path, split="train")
        elif ext == "csv": ds = load_dataset("csv", data_files=dataset_path, split="train")
        else: ds = load_dataset("json", data_files=dataset_path, split="train")
        log_training(f"Dataset loaded: {len(ds)} examples")
        
        output_name = config.get("output_name", f"lora_{int(time.time())}")
        output_path = os.path.join(LORA_DIR, output_name)
        
        trainer = SFTTrainer(
            model=model, tokenizer=tokenizer, train_dataset=ds,
            dataset_text_field=config.get("text_field", "text"),
            max_seq_length=config.get("max_seq_length", 2048),
            args=TrainingArguments(
                output_dir=os.path.join(OUTPUT_DIR, output_name),
                per_device_train_batch_size=config.get("batch_size", 2),
                gradient_accumulation_steps=config.get("grad_accum", 4),
                num_train_epochs=config.get("epochs", 3),
                learning_rate=config.get("learning_rate", 2e-4),
                fp16=True, logging_steps=1, save_strategy="epoch",
                warmup_steps=config.get("warmup_steps", 5),
            ),
        )
        
        log_training("Training started...")
        trainer.train()
        log_training("Training complete! Saving LoRA...")
        
        model.save_pretrained(output_path)
        tokenizer.save_pretrained(output_path)
        log_training(f"LoRA saved to {output_path}")
        
        with _lock:
            training_state["status"] = "complete"
            training_state["progress"] = 100
    except Exception as e:
        log_training(f"ERROR: {e}")
        with _lock:
            training_state["status"] = "error"

@app.route("/")
def index(): return render_template("index.html")

@app.route("/health")
def health(): return jsonify({"status": "ok"})

@app.route("/api/status")
def status():
    with _lock: return jsonify(dict(training_state))

@app.route("/api/models")
def list_models():
    models = []
    for f in os.listdir(MODEL_DIR):
        full = os.path.join(MODEL_DIR, f)
        if os.path.isfile(full):
            models.append({"name": f, "size_mb": round(os.path.getsize(full) / 1024 / 1024, 1)})
    return jsonify(models)

@app.route("/api/datasets")
def list_datasets():
    ds = []
    for f in os.listdir(DATASET_DIR):
        if f.endswith((".jsonl",".csv",".json")):
            full = os.path.join(DATASET_DIR, f)
            ds.append({"name": f, "size_mb": round(os.path.getsize(full) / 1024 / 1024, 1)})
    return jsonify(ds)

@app.route("/api/loras")
def list_loras():
    loras = []
    for f in os.listdir(LORA_DIR):
        full = os.path.join(LORA_DIR, f)
        if os.path.isdir(full):
            loras.append({"name": f})
    return jsonify(loras)

@app.route("/api/train", methods=["POST"])
def start_training():
    with _lock:
        if training_state["status"] == "training":
            return jsonify({"error": "Training already in progress"}), 409
    config = request.json or {}
    if not config.get("base_model"): return jsonify({"error": "base_model required"}), 400
    if not config.get("dataset"): return jsonify({"error": "dataset required"}), 400
    threading.Thread(target=run_training, args=(config,), daemon=True).start()
    return jsonify({"status": "started"})

# ── Node API ─────────────────────────────────────────────────
@app.route("/node/schema")
def node_schema():
    return jsonify({
        "name": "trainer",
        "description": "Fine-tune a model with LoRA using Unsloth",
        "inputs": [
            {"name": "base_model", "type": "string", "required": True},
            {"name": "dataset", "type": "string", "required": True},
            {"name": "epochs", "type": "number", "default": 3},
            {"name": "learning_rate", "type": "number", "default": 2e-4},
            {"name": "lora_r", "type": "number", "default": 16},
            {"name": "output_name", "type": "string", "required": False},
        ],
        "outputs": [
            {"name": "status", "type": "string"},
            {"name": "lora_path", "type": "string"},
        ]
    })

@app.route("/node/execute", methods=["POST"])
def node_execute():
    config = request.json or {}
    if not config.get("base_model") or not config.get("dataset"):
        return jsonify({"error": "base_model and dataset required"}), 400
    threading.Thread(target=run_training, args=(config,), daemon=True).start()
    return jsonify({"status": "started", "message": "Training kicked off. Poll /api/status for progress."})

if __name__ == "__main__": app.run(host="0.0.0.0", port=5000)
