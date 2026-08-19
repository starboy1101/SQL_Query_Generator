---
title: Prem 1B SQL API
emoji: 🗄️
colorFrom: green
colorTo: indigo
sdk: gradio
sdk_version: 6.24.0
python_version: 3.10.13
app_file: app.py
fullWidth: true
pinned: true
short_description: Schema-aware text-to-SQL inference
models:
  - prem-research/prem-1B-SQL
tags:
  - text-to-sql
  - sql
  - transformers
  - zerogpu
preload_from_hub:
  - prem-research/prem-1B-SQL config.json,generation_config.json,model-00001-of-00002.safetensors,model-00002-of-00002.safetensors,model.safetensors.index.json,special_tokens_map.json,tokenizer.json,tokenizer_config.json 44dd7fcf9227af4efed936bf29323c61bf66aad1
---

# Prem 1B SQL API

This Gradio Space provides the named `/generate` endpoint used by the SQL Pilot
FastAPI application. It generates SQL only. Schema allowlisting, AST validation,
row limits, and read-only execution remain inside the application backend.

The live deployment model is `prem-research/prem-1B-SQL`. Its metrics shown on
the Hugging Face model card are author-reported and are not measurements from
this portfolio application.
