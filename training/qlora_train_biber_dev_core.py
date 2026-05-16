from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.dataset_utils import format_training_text, load_jsonl, validate_dataset


DEFAULT_BASE_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"


def workspace_path(*parts: str) -> Path:
    root = Path("/workspace") if Path("/workspace").exists() else Path.cwd()
    return root.joinpath(*parts)


def configure_workspace_environment() -> None:
    if Path("/workspace").exists():
        os.environ.setdefault("HF_HOME", str(workspace_path(".hf_home")))
        os.environ.setdefault("PIP_CACHE_DIR", str(workspace_path("pip-cache")))
        os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="QLoRA fine-tune biber-dev-core.")
    parser.add_argument(
        "--base-model",
        "--base_model",
        default=os.getenv("BIBER_HF_MODEL", DEFAULT_BASE_MODEL),
    )
    parser.add_argument("--dataset", type=Path, default=workspace_path("data", "biber_train.jsonl"))
    parser.add_argument(
        "--output-dir",
        "--output_dir",
        type=Path,
        default=workspace_path("adapters", "biber-dev-core-lora"),
    )
    parser.add_argument(
        "--logging-dir",
        "--logging_dir",
        type=Path,
        default=workspace_path("outputs", "qlora-logs"),
    )
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--limit-samples", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--min-records", type=int, default=1)

    parser.add_argument("--num-train-epochs", type=float, default=1.0)
    parser.add_argument("--max-steps", type=int, default=-1)
    parser.add_argument("--per-device-train-batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--warmup-ratio", type=float, default=0.03)
    parser.add_argument("--logging-steps", type=int, default=10)
    parser.add_argument("--save-steps", type=int, default=100)
    parser.add_argument("--save-total-limit", type=int, default=3)
    parser.add_argument("--resume-from-checkpoint", default=None)

    parser.add_argument("--precision", choices=("auto", "bf16", "fp16", "fp32"), default="auto")
    parser.add_argument("--no-4bit", action="store_true")
    parser.add_argument("--gradient-checkpointing", action="store_true")
    parser.add_argument("--trust-remote-code", action="store_true")

    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument(
        "--lora-target-modules",
        default="q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj",
    )
    return parser.parse_args()


def require_training_dependencies() -> dict[str, Any]:
    try:
        import torch
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from torch.utils.data import Dataset
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            BitsAndBytesConfig,
            DataCollatorForLanguageModeling,
            Trainer,
            TrainingArguments,
        )
    except ImportError as exc:
        raise SystemExit(
            "Missing training dependency. Install GPU training requirements first:\n"
            "  /workspace/biber-venv/bin/python -m pip install -r requirements-training.txt\n"
            f"Original error: {exc}"
        ) from exc

    return {
        "torch": torch,
        "Dataset": Dataset,
        "AutoModelForCausalLM": AutoModelForCausalLM,
        "AutoTokenizer": AutoTokenizer,
        "BitsAndBytesConfig": BitsAndBytesConfig,
        "DataCollatorForLanguageModeling": DataCollatorForLanguageModeling,
        "LoraConfig": LoraConfig,
        "Trainer": Trainer,
        "TrainingArguments": TrainingArguments,
        "get_peft_model": get_peft_model,
        "prepare_model_for_kbit_training": prepare_model_for_kbit_training,
    }


def choose_precision(torch: Any, precision: str) -> tuple[Any, bool, bool]:
    if precision == "bf16" or (
        precision == "auto" and torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    ):
        return torch.bfloat16, True, False
    if precision == "fp16" or (precision == "auto" and torch.cuda.is_available()):
        return torch.float16, False, True
    return torch.float32, False, False


def build_dataset_class(
    dataset_base: type,
    records: list[dict[str, Any]],
    tokenizer: Any,
    max_len: int,
):
    class JsonlSFTDataset(dataset_base):
        def __len__(self) -> int:
            return len(records)

        def __getitem__(self, index: int) -> dict[str, list[int]]:
            text = format_training_text(records[index], eos_token=tokenizer.eos_token)
            tokenized = tokenizer(text, truncation=True, max_length=max_len, padding=False)
            tokenized["labels"] = list(tokenized["input_ids"])
            return tokenized

    return JsonlSFTDataset()


def main() -> int:
    configure_workspace_environment()
    args = parse_args()
    result = validate_dataset(args.dataset, min_records=args.min_records)
    if not result.ok:
        for issue in result.errors:
            print(f"ERROR line {issue.line_number}: {issue.message}")
        return 1

    records = load_jsonl(args.dataset)
    if args.limit_samples is not None:
        records = records[: args.limit_samples]

    print("BIBER QLoRA training")
    print(f"Base model: {args.base_model}")
    print(f"Dataset:    {args.dataset} ({len(records)} records)")
    print(f"Output:     {args.output_dir}")
    print(f"Logs:       {args.logging_dir}")

    if args.dry_run:
        print()
        print("Dry run only. First formatted example:")
        print(format_training_text(records[0] if records else {}))
        return 0

    deps = require_training_dependencies()
    torch = deps["torch"]
    dtype, bf16, fp16 = choose_precision(torch, args.precision)
    tokenizer = deps["AutoTokenizer"].from_pretrained(
        args.base_model,
        trust_remote_code=args.trust_remote_code,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    quantization_config = None
    if not args.no_4bit:
        quantization_config = deps["BitsAndBytesConfig"](
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=dtype,
            bnb_4bit_use_double_quant=True,
        )

    model = deps["AutoModelForCausalLM"].from_pretrained(
        args.base_model,
        device_map="auto",
        quantization_config=quantization_config,
        torch_dtype=dtype,
        trust_remote_code=args.trust_remote_code,
    )
    model.config.use_cache = False
    if not args.no_4bit:
        model = deps["prepare_model_for_kbit_training"](
            model,
            use_gradient_checkpointing=args.gradient_checkpointing,
        )

    lora_config = deps["LoraConfig"](
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            item.strip()
            for item in args.lora_target_modules.split(",")
            if item.strip()
        ],
    )
    model = deps["get_peft_model"](model, lora_config)
    model.print_trainable_parameters()

    train_dataset = build_dataset_class(
        deps["Dataset"],
        records,
        tokenizer,
        args.max_seq_length,
    )
    data_collator = deps["DataCollatorForLanguageModeling"](tokenizer=tokenizer, mlm=False)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.logging_dir.mkdir(parents=True, exist_ok=True)

    training_args = deps["TrainingArguments"](
        output_dir=str(args.output_dir),
        logging_dir=str(args.logging_dir),
        per_device_train_batch_size=args.per_device_train_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.learning_rate,
        num_train_epochs=args.num_train_epochs,
        max_steps=args.max_steps,
        warmup_ratio=args.warmup_ratio,
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        save_total_limit=args.save_total_limit,
        bf16=bf16,
        fp16=fp16,
        gradient_checkpointing=args.gradient_checkpointing,
        optim="paged_adamw_8bit" if not args.no_4bit else "adamw_torch",
        report_to="none",
        remove_unused_columns=False,
    )
    trainer = deps["Trainer"](
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        data_collator=data_collator,
    )
    trainer.train(resume_from_checkpoint=args.resume_from_checkpoint)
    trainer.model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print(f"Saved LoRA adapter to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
