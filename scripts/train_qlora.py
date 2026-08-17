from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SYSTEM_PROMPT = """You are an expert data analyst who writes precise, read-only SQL.
Return exactly one SQL SELECT statement and no commentary. Use only the provided schema.
Never invent identifiers or use data-changing operations."""


def format_example(example: dict[str, Any]) -> tuple[str, str]:
    dialect = str(example.get("dialect", "sqlite"))
    prompt = (
        f"<s>[INST] {SYSTEM_PROMPT}\n\n"
        f"SQL dialect: {dialect}\n"
        f"DATABASE SCHEMA\n{example['schema']}\n\n"
        f"USER QUESTION\n{example['question']}\n\nSQL [/INST]"
    )
    answer = f"\n{str(example['sql']).strip()}</s>"
    return prompt, answer


@dataclass
class CompletionOnlyCollator:
    tokenizer: Any

    def __call__(self, features: list[dict[str, Any]]) -> dict[str, Any]:
        import torch

        max_length = max(len(feature["input_ids"]) for feature in features)
        input_ids, attention_masks, labels = [], [], []
        pad_id = self.tokenizer.pad_token_id
        for feature in features:
            padding = max_length - len(feature["input_ids"])
            input_ids.append(feature["input_ids"] + [pad_id] * padding)
            attention_masks.append(feature["attention_mask"] + [0] * padding)
            labels.append(feature["labels"] + [-100] * padding)
        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "attention_mask": torch.tensor(attention_masks, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fine-tune CodeLlama for text-to-SQL with QLoRA")
    parser.add_argument(
        "--train-file", type=Path, required=True, help="JSONL: question, schema, sql, dialect"
    )
    parser.add_argument("--validation-file", type=Path)
    parser.add_argument("--model", default="codellama/CodeLlama-7b-Instruct-hf")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/codellama-text-to-sql-qlora"))
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=16)
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--lora-r", type=int, default=64)
    parser.add_argument("--lora-alpha", type=int, default=16)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    import torch
    from datasets import load_dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        Trainer,
        TrainingArguments,
        set_seed,
    )

    if not torch.cuda.is_available():
        raise RuntimeError("QLoRA training requires a CUDA-capable GPU")
    set_seed(args.seed)
    data_files = {"train": str(args.train_file)}
    if args.validation_file:
        data_files["validation"] = str(args.validation_file)
    dataset = load_dataset("json", data_files=data_files)
    if "validation" not in dataset:
        split = dataset["train"].train_test_split(test_size=0.02, seed=args.seed)
        dataset["train"], dataset["validation"] = split["train"], split["test"]

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    tokenizer.pad_token = tokenizer.pad_token or tokenizer.eos_token
    tokenizer.padding_side = "right"

    def tokenize(example: dict[str, Any]) -> dict[str, Any]:
        prompt, answer = format_example(example)
        prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
        full = tokenizer(
            prompt + answer,
            add_special_tokens=False,
            truncation=True,
            max_length=args.max_length,
        )
        labels = list(full["input_ids"])
        prompt_length = min(len(prompt_ids), len(labels))
        labels[:prompt_length] = [-100] * prompt_length
        full["labels"] = labels
        return full

    tokenized = dataset.map(tokenize, remove_columns=dataset["train"].column_names, desc="Tokenizing")
    compute_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        device_map="auto",
        quantization_config=quantization,
        torch_dtype=compute_dtype,
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(
        model,
        LoraConfig(
            r=args.lora_r,
            lora_alpha=args.lora_alpha,
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        ),
    )
    training_args = TrainingArguments(
        output_dir=str(args.output_dir),
        num_train_epochs=args.epochs,
        learning_rate=args.learning_rate,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        gradient_checkpointing=True,
        eval_strategy="steps",
        eval_steps=250,
        save_steps=250,
        logging_steps=10,
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        bf16=torch.cuda.is_bf16_supported(),
        fp16=not torch.cuda.is_bf16_supported(),
        optim="paged_adamw_8bit",
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        report_to="none",
        seed=args.seed,
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["validation"],
        data_collator=CompletionOnlyCollator(tokenizer),
    )
    trainer.train()
    trainer.save_model(str(args.output_dir))
    tokenizer.save_pretrained(str(args.output_dir))
    print(f"Saved QLoRA adapter and tokenizer to {args.output_dir}")


if __name__ == "__main__":
    main()
