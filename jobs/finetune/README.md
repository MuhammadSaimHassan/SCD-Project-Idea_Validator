# M10t Fine-Tuning Pipeline (Colab / Kaggle QLoRA -> GGUF)

This folder implements the offline fine-tuning workflow (`M10t`) for the 1B–3B scoring model (`Qwen/Qwen2.5-1.5B-Instruct`).

## 1. Build the Dataset (>=300 examples, >=60 human-checked, split by `idea_id`)

```bash
python -m jobs.finetune.src.build_dataset \
  --cards data/snapshot/cards.jsonl \
  --out-dir jobs/finetune/data \
  --num-ideas 65
```

This creates:
- `jobs/finetune/data/train.jsonl` (312 examples across 52 ideas)
- `jobs/finetune/data/eval_checked.jsonl` (78 hand-checked examples across 13 ideas)
- Zero `idea_id` overlap between train and eval, and zero overlap with Phase 8 verdict tuning ideas.

## 2. Train QLoRA on Free GPU (Google Colab T4 or Kaggle)

Hyperparameters are tracked in `jobs/finetune/config.yaml` (`r=16`, `lora_alpha=32`, `lr=2e-4`, `epochs=3`, `batch_size=4`).

```bash
pip install torch transformers datasets peft trl bitsandbytes accelerate pyyaml
python -m jobs.finetune.src.train_qlora \
  --config jobs/finetune/config.yaml \
  --train jobs/finetune/data/train_messages.jsonl \
  --eval jobs/finetune/data/eval_checked.jsonl \
  --out artifacts
```

## 3. Convert & Quantise to GGUF for CPU Serving (Never Commit Weights to Git)

```bash
git clone https://github.com/ggml-org/llama.cpp
python llama.cpp/convert_hf_to_gguf.py artifacts/merged --outfile artifacts/scorer-1.5b-f16.gguf
./llama.cpp/build/bin/llama-quantize artifacts/scorer-1.5b-f16.gguf artifacts/scorer-1.5b-q4_k_m.gguf Q4_K_M
```

Upload `scorer-1.5b-q4_k_m.gguf` as a GitHub Release asset and pass its URL via `MODEL_DOWNLOAD_URL` / initContainer in Kubernetes.

## 4. Evaluate Base vs Fine-Tuned vs Hosted

```bash
python -m jobs.finetune.src.evaluate_models --eval jobs/finetune/data/eval_checked.jsonl
```
