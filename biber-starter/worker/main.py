import os
import time
import subprocess

def gpu_status():
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,utilization.gpu", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip()
    except Exception as exc:
        return f"nvidia-smi unavailable: {exc}"

def main():
    print("BIBER worker started")
    print("GPU status:")
    print(gpu_status())

    # Starter placeholder: real implementation should pull jobs from Redis/MySQL.
    while True:
        print("Worker heartbeat. Waiting for scheduler/queue integration...")
        time.sleep(30)

if __name__ == "__main__":
    main()
