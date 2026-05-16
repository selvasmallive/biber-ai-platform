#!/usr/bin/env bash
set -e

echo "=== BIBER GPU CHECK ==="
echo "Hostname: $(hostname)"
echo "User: $(whoami)"
echo

if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi
else
  echo "nvidia-smi not found. Make sure your Vast.ai image has NVIDIA drivers/CUDA."
  exit 1
fi

echo
echo "Docker version:"
docker --version || true

echo
echo "Docker GPU test:"
docker run --rm --gpus all nvidia/cuda:12.4.1-runtime-ubuntu22.04 nvidia-smi || true
