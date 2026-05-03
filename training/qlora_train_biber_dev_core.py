"""
Starter QLoRA training script for biber-dev-core.

This is a template. You must provide:
- A base model path or Hugging Face model id
- A JSONL dataset with instruction/input/output fields
- Enough GPU VRAM or use 4-bit quantization

Example:
python training/qlora_train_biber_dev_core.py \
  --base_model /models/base \
  --dataset data/train.jsonl \
  --output_dir models/biber-dev-core-lora
"""

import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_model", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output_dir", required=True)
    args = parser.parse_args()

    print("BIBER QLoRA training template")
    print(f"Base model: {args.base_model}")
    print(f"Dataset: {args.dataset}")
    print(f"Output: {args.output_dir}")
    print()
    print("Next implementation step:")
    print("- Add transformers AutoModelForCausalLM")
    print("- Add BitsAndBytesConfig 4-bit")
    print("- Add PEFT LoraConfig")
    print("- Add SFTTrainer or custom Trainer")
    print("- Save LoRA adapter")

if __name__ == "__main__":
    main()
