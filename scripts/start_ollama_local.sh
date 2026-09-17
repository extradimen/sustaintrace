#!/bin/sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
model_store="$project_root/models/ollama"
mkdir -p "$model_store"
export OLLAMA_MODELS="$model_store"

exec ollama serve
