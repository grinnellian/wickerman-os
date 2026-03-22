"""Wickerman OS v5.2.0 — Model Trainer plugin manifest."""
from pathlib import Path

_FILES_DIR = Path(__file__).parent.parent / "src" / "plugins" / "trainer"

PLUGIN_HOST = ("127.0.0.1", "trainer.wickerman.local")

WM_TRAINER = {'name': 'Model Trainer', 'description': 'LoRA fine-tuning with Unsloth — fast local training on your GPU', 'icon': 'model_training', 'build': True, 'build_context': 'data', 'container_name': 'wm-trainer', 'url': 'http://trainer.wickerman.local', 'ports': [5000], 'gpu': True, 'env': ['MODEL_DIR=/models', 'DATASET_DIR=/datasets', 'LORA_DIR=/loras', 'OUTPUT_DIR=/data/outputs'], 'volumes': ['{models}:/models', '{datasets}:/datasets', '{loras}:/loras', '{self}/data:/data'], 'nginx_host': 'trainer.wickerman.local', 'help': '## Model Trainer (Unsloth)\nFast LoRA fine-tuning on your local GPU.\n\n**Workflow:** Select a base model from /models, point to a dataset, configure training params, hit Train.\n\n**Output:** LoRA adapters saved to ~/WickermanSupport/loras/\n\n**Node API:** POST `/node/execute` with base_model, dataset, epochs, learning_rate to trigger training from wm-flow.\n\n**Formats:** Supports JSONL, CSV, and Alpaca-format datasets.'}

WM_TRAINER_FILES = {
    "data/Dockerfile": (_FILES_DIR / "Dockerfile").read_text(),
    "data/app.py": (_FILES_DIR / "app.py").read_text(),
    "data/templates/index.html": (_FILES_DIR / "templates" / "index.html").read_text(),
}

WM_TRAINER["files"] = WM_TRAINER_FILES
