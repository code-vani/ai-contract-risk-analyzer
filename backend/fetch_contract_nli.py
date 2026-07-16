"""
Run once: pulls the ContractNLI contradiction-labelled pairs from the
working HuggingFace mirror (kiddothe2b/contract-nli), since
stanfordnlp/contract_nli 401s / no longer resolves on the Hub.

Lists the actual Parquet filenames on the auto-converted
refs/convert/parquet branch (rather than guessing "0000.parquet") and
downloads whichever ones exist for the contractnli_a config. This avoids
datasets.load_dataset(), which fails with "Dataset scripts are no longer
supported" on this repo (it ships a legacy loading script).
"""
import json
import pandas as pd
from huggingface_hub import HfApi, hf_hub_download

REPO_ID = "kiddothe2b/contract-nli"
REVISION = "refs/convert/parquet"
CONFIG = "contractnli_a"

api = HfApi()
all_files = api.list_repo_files(repo_id=REPO_ID, repo_type="dataset", revision=REVISION)
parquet_files = [f for f in all_files if f.startswith(CONFIG) and f.endswith(".parquet")]

if not parquet_files:
    raise SystemExit(
        f"No parquet files found under '{CONFIG}' on {REPO_ID}@{REVISION}. "
        f"Files seen: {all_files}"
    )

print(f"Found {len(parquet_files)} parquet file(s): {parquet_files}")

frames = []
for rel_path in parquet_files:
    print(f"Downloading {rel_path}...")
    local_path = hf_hub_download(
        repo_id=REPO_ID, repo_type="dataset", revision=REVISION, filename=rel_path
    )
    frames.append(pd.read_parquet(local_path))

df = pd.concat(frames, ignore_index=True)
print(f"Loaded {len(df)} total rows")

contradictions = df[df["label"] == 0]  # 0 = contradiction
print(f"{len(contradictions)} rows labelled 'contradiction'")

records = contradictions[["premise", "hypothesis", "label"]].to_dict(orient="records")
with open("contract_nli.json", "w", encoding="utf-8") as f:
    json.dump(records, f)

print(f"Saved {len(records)} contradiction pairs to contract_nli.json")
