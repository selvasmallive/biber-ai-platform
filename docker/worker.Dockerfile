FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

WORKDIR /worker

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-worker.txt /worker/requirements-worker.txt
RUN pip3 install --no-cache-dir -r /worker/requirements-worker.txt

COPY worker /worker/worker
