"""Colab / Kaggle QLoRA fine-tuning script for M10 1.5B scorer model (PEFT + TRL).

Run on a free GPU (Colab T4 or Kaggle P100) after installing:
  pip install torch transformers datasets peft trl bitsandbytes accelerate pyyaml
"""

import argparse
from pathlib import Path
from typing import Any

import yaml


def load_finetune_config(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid config: {path}")
    return data


def train_qlora(
    config_path: Path,
    train_jsonl: Path,
    eval_jsonl: Path,
    output_dir: Path,
) -> None:
    """Train LoRA adapter on 4-bit quantized base model and merge adapter."""
    import torch  # type: ignore[import-not-found]
    from datasets import load_dataset  # type: ignore[import-not-found]
    from peft import LoraConfig, PeftModel  # type: ignore[import-not-found]
    from transformers import (  # type: ignore[import-not-found]
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
    )
    from trl import SFTConfig, SFTTrainer  # type: ignore[import-not-found]

    cfg = load_finetune_config(config_path)
    base_model = str(cfg["base_model"])
    lora_cfg = cfg["lora"]
    train_cfg = cfg["training"]

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )

    peft_config = LoraConfig(
        r=int(lora_cfg["r"]),
        lora_alpha=int(lora_cfg["lora_alpha"]),
        lora_dropout=float(lora_cfg["lora_dropout"]),
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=list(lora_cfg["target_modules"]),
    )

    ds = load_dataset(
        "json",
        data_files={"train": str(train_jsonl), "validation": str(eval_jsonl)},
    )

    sft_args = SFTConfig(
        output_dir=str(output_dir / "checkpoints"),
        num_train_epochs=int(train_cfg["num_train_epochs"]),
        per_device_train_batch_size=int(train_cfg["per_device_train_batch_size"]),
        gradient_accumulation_steps=int(train_cfg["gradient_accumulation_steps"]),
        learning_rate=float(train_cfg["learning_rate"]),
        warmup_ratio=float(train_cfg["warmup_ratio"]),
        eval_strategy=str(train_cfg["eval_strategy"]),
        logging_steps=10,
        save_strategy="epoch",
        fp16=True,
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        args=sft_args,
        train_dataset=ds["train"],
        eval_dataset=ds["validation"],
        peft_config=peft_config,
        processing_class=tokenizer,
    )
    trainer.train()

    adapter_dir = output_dir / "adapter"
    trainer.model.save_pretrained(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))

    # Merge adapter into FP16 base model for GGUF conversion
    base_fp16 = AutoModelForCausalLM.from_pretrained(
        base_model, torch_dtype=torch.float16, device_map="cpu"
    )
    merged = PeftModel.from_pretrained(base_fp16, str(adapter_dir)).merge_and_unload()
    merged_dir = output_dir / "merged"
    merged.save_pretrained(str(merged_dir))
    tokenizer.save_pretrained(str(merged_dir))
    print(f"Saved merged model to {merged_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train M10 QLoRA scorer on Colab/Kaggle")
    parser.add_argument("--config", default="jobs/finetune/config.yaml")
    parser.add_argument("--train", default="jobs/finetune/data/train_messages.jsonl")
    parser.add_argument("--eval", default="jobs/finetune/data/eval_checked.jsonl")
    parser.add_argument("--out", default="artifacts")
    args = parser.parse_args()
    train_qlora(Path(args.config), Path(args.train), Path(args.eval), Path(args.out))


if __name__ == "__main__":
    main()
