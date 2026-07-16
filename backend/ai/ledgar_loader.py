import os
import json
import pyarrow as pa
from config import LEDGAR_DIR

# Maps our internal clause type names → LEDGAR label names
# Label names sourced from ledgar/train/dataset_info.json
CLAUSE_TYPES = {
    "payment":         "Payments",
    "termination":     "Terminations",
    "liability":       "Indemnifications",
    "liability_cap":   "Indemnity",
    "confidentiality": "Confidentiality",
    "ip":              "Intellectual Property",
    "governing_law":   "Governing Laws",
    "warranties":      "Warranties",
    "dispute":         "Arbitration",
    "non_compete":     "Non-Disparagement",
}

_ARROW_FILE = os.path.join(LEDGAR_DIR, "train", "data-00000-of-00001.arrow")
_INFO_FILE  = os.path.join(LEDGAR_DIR, "train", "dataset_info.json")


def load_ledgar_examples(n_examples: int = 2) -> dict:
    """
    Load LEDGAR Arrow file and return 2 real clause examples per type.
    Called once at startup — stored in LEDGAR_EXAMPLES constant.

    LEDGAR stores labels as integers. We read the names list from
    dataset_info.json to map int → string.

    Returns:
        { "payment": ["All invoices shall...", "Payment is due..."], ... }
    """
    print("[LEDGAR] Loading few-shot examples...")
    empty = {key: [] for key in CLAUSE_TYPES}

    if not os.path.exists(_ARROW_FILE):
        print(f"[LEDGAR] Arrow file not found at {_ARROW_FILE}. Using empty examples.")
        return empty

    try:
        # Read label names from metadata
        with open(_INFO_FILE) as f:
            info = json.load(f)
        label_names = info["features"]["label"]["names"]

        # HuggingFace saves Arrow in stream format — use open_stream not open_file
        reader = pa.ipc.open_stream(_ARROW_FILE)
        table  = reader.read_all()
        texts  = table.column("text").to_pylist()
        labels = table.column("label").to_pylist()  # integers

        # Build a dict: label_name → list of clause texts
        by_label: dict[str, list] = {}
        for text, label_idx in zip(texts, labels):
            name = label_names[label_idx]
            if name not in by_label:
                by_label[name] = []
            if len(by_label[name]) < n_examples:
                by_label[name].append(text.strip()[:350])

        examples = {}
        for our_type, ledgar_name in CLAUSE_TYPES.items():
            examples[our_type] = by_label.get(ledgar_name, [])

        loaded = sum(len(v) for v in examples.values())
        print(f"[LEDGAR] Ready — {loaded} examples across {len(examples)} clause types")
        return examples

    except Exception as e:
        print(f"[LEDGAR] Load failed: {e}. Using empty examples.")
        return empty


# Loaded once at import — reused across all API calls, zero extra latency per request
LEDGAR_EXAMPLES = load_ledgar_examples()
