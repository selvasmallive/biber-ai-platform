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
