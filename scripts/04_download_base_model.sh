#!/usr/bin/env bash
set -e

mkdir -p models

cat <<'MSG'
This script is a placeholder.

For your first practical local model, use a coding-friendly 7B instruct model.
Examples you can evaluate:
- Qwen2.5-Coder-7B-Instruct
- DeepSeek-Coder-6.7B-Instruct
- CodeLlama-7B-Instruct

Download method depends on licensing and Hugging Face access.
Example pattern:

huggingface-cli login
huggingface-cli download <model-id> --local-dir models/biber-dev-core-base

Then update worker/model loading code.
MSG
