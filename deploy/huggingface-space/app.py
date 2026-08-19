# ruff: noqa: I001
from __future__ import annotations

import re

# ZeroGPU patches torch when spaces is imported, so this import must remain first.
import spaces
import gradio as gr
import torch
from transformers import AutoModelForCausalLM, PreTrainedTokenizerFast


MODEL_ID = "prem-research/prem-1B-SQL"
MODEL_REVISION = "44dd7fcf9227af4efed936bf29323c61bf66aad1"

MAX_INPUT_TOKENS = 3072
DEFAULT_MAX_NEW_TOKENS = 128
MAX_NEW_TOKENS = 256
MAX_OUTPUT_CHARS = 20_000

tokenizer = PreTrainedTokenizerFast.from_pretrained(
    MODEL_ID,
    revision=MODEL_REVISION,
)
if not tokenizer.is_fast:
    raise RuntimeError("Prem-1B-SQL requires the fast byte-level tokenizer")
tokenizer.padding_side = "right"
tokenizer.pad_token = tokenizer.eos_token

# Transformers 5 can otherwise select the slow Llama tokenizer declared in
# this checkpoint and expose its internal space/newline pieces as literal text.
DECODE_PROBE = "SELECT count(*) FROM customers;\n"
decode_probe_ids = tokenizer.encode(DECODE_PROBE, add_special_tokens=False)
decoded_probe = tokenizer.decode(
    decode_probe_ids,
    skip_special_tokens=True,
    clean_up_tokenization_spaces=False,
)
if decoded_probe != DECODE_PROBE:
    raise RuntimeError("Prem-1B-SQL tokenizer failed its byte-level decode check")

# ZeroGPU requires the GPU-backed model to be placed on CUDA at module load.
model = (
    AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        revision=MODEL_REVISION,
        dtype=torch.float16,
        use_safetensors=True,
    )
    .to("cuda")
    .eval()
)

SQL_START = re.compile(r"^\s*(?:WITH|SELECT)\b", re.IGNORECASE | re.MULTILINE)
CODE_BLOCK = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
INVALID_DECODE_MARKERS = ("Ċ", "Ġ")

EXAMPLE_PROMPT = """# Follow these instructions:
You will be given table schemas for a database. Write one correct, read-only SQL query
that answers the question.

1. Return SQL only, on one line, without Markdown or commentary.
2. Use only tables and columns present in the schema; never invent identifiers.
3. Never use INSERT, UPDATE, DELETE, DDL, or PRAGMA.

# SQL dialect: sqlite
# Maximum rows: 100

# Database and Table Schema:
TABLE customers (id INTEGER PK NOT NULL, name TEXT NOT NULL, city TEXT)

# Here are some Examples on how to generate SQL statements and use column names:

# Question: How many customers are there?

# SQL:"""


def extract_sql(generated: str) -> str:
    text = generated.strip()

    fenced = CODE_BLOCK.search(text)
    if fenced:
        text = fenced.group(1).strip()

    # Some checkpoints repeat the training delimiter before the answer.
    if "# SQL:" in text:
        text = text.rsplit("# SQL:", maxsplit=1)[-1].strip()

    start = SQL_START.search(text)
    if not start:
        raise gr.Error("The model did not return a SQL SELECT statement.")

    sql = text[start.start() :].removesuffix("```").strip()
    if not sql:
        raise gr.Error("The model returned an empty response.")
    if len(sql) > MAX_OUTPUT_CHARS:
        raise gr.Error("The model response was unexpectedly large.")
    if "\x00" in sql or any(marker in sql for marker in INVALID_DECODE_MARKERS):
        raise gr.Error("The model returned malformed tokenizer output. Please retry.")
    return sql


@spaces.GPU(duration=45)
def generate_sql(prompt: str, max_new_tokens: int) -> str:
    normalized_prompt = (prompt or "").strip()
    if not normalized_prompt:
        raise gr.Error("Prompt cannot be empty.")

    token_limit = max(
        32,
        min(MAX_NEW_TOKENS, int(max_new_tokens or DEFAULT_MAX_NEW_TOKENS)),
    )
    inputs = tokenizer(
        normalized_prompt,
        return_tensors="pt",
        add_special_tokens=True,
        truncation=False,
    )
    input_length = int(inputs["input_ids"].shape[-1])
    if input_length > MAX_INPUT_TOKENS:
        raise gr.Error(
            f"Prompt has {input_length:,} tokens; the maximum is {MAX_INPUT_TOKENS:,}."
        )

    inputs = {name: tensor.to("cuda") for name, tensor in inputs.items()}
    with torch.inference_mode():
        output = model.generate(
            **inputs,
            max_new_tokens=token_limit,
            do_sample=False,
            num_beams=1,
            eos_token_id=tokenizer.eos_token_id,
            pad_token_id=tokenizer.pad_token_id,
            stop_strings=[";\n", "\n#"],
            tokenizer=tokenizer,
            use_cache=True,
        )

    generated_token_ids = output[0, input_length:].tolist()
    generated = tokenizer.decode(
        generated_token_ids,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )
    return extract_sql(generated)


with gr.Blocks(title="Prem 1B SQL API") as demo:
    gr.Markdown(
        """
        # Prem 1B SQL

        Generate SQL from a schema-aware prompt. The calling application must
        validate every generated statement before execution.
        """
    )
    prompt_input = gr.Textbox(
        value=EXAMPLE_PROMPT,
        label="Schema-aware prompt",
        lines=20,
    )
    max_tokens_input = gr.Slider(
        minimum=32,
        maximum=MAX_NEW_TOKENS,
        value=DEFAULT_MAX_NEW_TOKENS,
        step=1,
        label="Maximum output tokens",
    )
    generate_button = gr.Button("Generate SQL", variant="primary")
    sql_output = gr.Code(label="Generated SQL", language="sql")

    generate_button.click(
        fn=generate_sql,
        inputs=[prompt_input, max_tokens_input],
        outputs=sql_output,
        api_name="generate",
        concurrency_limit=1,
    )

demo.queue(max_size=20, default_concurrency_limit=1)

if __name__ == "__main__":
    demo.launch()
