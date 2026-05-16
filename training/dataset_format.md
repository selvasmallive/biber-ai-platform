# BIBER Training Dataset Format

Use JSONL.

Each line:

```json
{
  "instruction": "Fix this Python FastAPI bug",
  "input": "Traceback or code here",
  "output": "Corrected code or patch here",
  "category": "python",
  "stack": ["python", "fastapi"],
  "quality": "verified"
}
```

Recommended categories:

- python
- react
- dotnet
- java
- rust
- mysql
- azure
- ffmpeg
- video
- audio
- proctoring

Important:
- Prefer verified examples with tests.
- Avoid private/customer code unless you have permission.
- Remove secrets.

## Validate Before Training

Store real datasets on the Vast 500 GB volume, not in git:

```bash
/workspace/data/biber_train.jsonl
```

Validate the dataset before starting a long GPU job:

```bash
cd /workspace/biber-ai-platform
/workspace/biber-venv/bin/python training/validate_dataset.py \
  --dataset /workspace/data/biber_train.jsonl \
  --min-records 10 \
  --report /workspace/outputs/dataset-validation.json \
  --print-sample
```

Use the tiny repository sample only for smoke tests:

```bash
python training/validate_dataset.py \
  --dataset training/sample_dataset.jsonl \
  --print-sample
```

## Training Output Paths

Keep generated training artifacts on the Vast volume:

```text
/workspace/data          # JSONL datasets
/workspace/checkpoints   # intermediate checkpoints
/workspace/adapters      # LoRA/QLoRA adapters
/workspace/outputs       # logs, reports, evaluations
```

## Internet Dataset Ingestion

Internet data must come through the approved-source manifest. Do not run broad
web scraping or recursive crawling for training data.

Default approved-source manifest:

```text
training/approved_sources.json
```

The ingestion script enforces:

- `enabled: true`
- `approved: true`
- license present in the manifest allowlist
- URL domain present in the manifest allowlist
- attribution text
- JSONL records that validate against the BIBER dataset schema
- secret filtering and deduplication

Run a bounded ingestion on Vast:

```bash
cd /workspace/biber-ai-platform
bash scripts/vast_ingest_internet_dataset.sh /workspace/data/biber_train_internet.jsonl
```

The script writes only to the 500 GB Vast volume:

```text
/workspace/data/raw
/workspace/data/biber_train_internet.jsonl
/workspace/outputs/dataset-provenance.json
/workspace/outputs/internet-dataset-validation.json
```

For long ingestion jobs, run the script in `tmux` and disconnect while the GPU
machine works:

```bash
tmux new -s biber-ingest -- \
  bash scripts/vast_ingest_internet_dataset.sh /workspace/data/biber_train_internet.jsonl
```

Only promote the output to `/workspace/data/biber_train.jsonl` after reviewing
the provenance and validation report.
