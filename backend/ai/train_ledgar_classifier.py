"""
Train a TF-IDF + Logistic Regression classifier on the LEDGAR dataset.

Run once from the backend/ directory:
    python ai/train_ledgar_classifier.py

Output: backend/ai/ledgar_classifier.pkl (~5-10 MB)
Training time: ~30-60 seconds on any CPU (no GPU needed).

The trained model is used by hybrid_extractor.py to classify clause types
without any Gemini API call.
"""

import json
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pyarrow as pa
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from config import LEDGAR_DIR
from ai.ledgar_loader import CLAUSE_TYPES

# Where to save the trained model
MODEL_PATH = os.path.join(os.path.dirname(__file__), "ledgar_classifier.pkl")

# Reverse map: LEDGAR label name (e.g. "Payments") → our type (e.g. "payment")
_LEDGAR_TO_OURS = {ledgar: ours for ours, ledgar in CLAUSE_TYPES.items()}


def train():
    arrow_path = os.path.join(LEDGAR_DIR, "train", "data-00000-of-00001.arrow")
    info_path  = os.path.join(LEDGAR_DIR, "train", "dataset_info.json")

    if not os.path.exists(arrow_path):
        print(f"[Trainer] ERROR: LEDGAR arrow file not found at {arrow_path}")
        print("[Trainer] Make sure Data_sets_hackathon/ is present locally.")
        sys.exit(1)

    print("[Trainer] Loading LEDGAR dataset (60K examples)...")
    with open(info_path) as f:
        info = json.load(f)
    label_names = info["features"]["label"]["names"]

    reader = pa.ipc.open_stream(arrow_path)
    table  = reader.read_all()
    texts  = table.column("text").to_pylist()
    labels = table.column("label").to_pylist()

    print(f"[Trainer] {len(texts)} examples, {len(label_names)} LEDGAR label types")

    # Map every LEDGAR label to our 10 clause types.
    # Any label not in our mapping becomes "other" — still useful training signal.
    mapped = [_LEDGAR_TO_OURS.get(label_names[idx], "other") for idx in labels]

    from collections import Counter
    dist = Counter(mapped)
    print("[Trainer] Mapped label distribution:")
    for label, count in sorted(dist.items(), key=lambda x: -x[1]):
        print(f"  {label:20s}: {count:,}")

    print("\n[Trainer] Training TF-IDF + LogisticRegression (no GPU needed)...")
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2),   # unigrams + bigrams catch phrase patterns
            max_features=60_000,  # vocabulary cap — keeps model compact
            min_df=2,             # ignore terms appearing only once
            sublinear_tf=True,    # log(1+tf) scaling reduces impact of repeated words
            strip_accents="unicode",
            lowercase=True,
        )),
        ("clf", LogisticRegression(
            C=5.0,          # regularisation — works well for text classification
            max_iter=1000,
            solver="lbfgs",
            class_weight="balanced",  # upweights minority classes (ip, dispute, non_compete)
            n_jobs=-1,      # use all CPU cores
        )),
    ])

    pipeline.fit(texts, mapped)
    print("[Trainer] Training complete.")

    # Quick sanity check on a small sample
    sample_texts = texts[:200]
    sample_true  = mapped[:200]
    sample_preds = pipeline.predict(sample_texts)
    correct = sum(p == t for p, t in zip(sample_preds, sample_true))
    print(f"[Trainer] Sample accuracy (first 200): {correct/200:.0%}")

    # Save
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(pipeline, f)
    size_mb = os.path.getsize(MODEL_PATH) / 1_048_576
    print(f"\n[Trainer] Saved to {MODEL_PATH}  ({size_mb:.1f} MB)")
    print("[Trainer] Done. Component 2 will now use this model for structured contracts.")


if __name__ == "__main__":
    train()
