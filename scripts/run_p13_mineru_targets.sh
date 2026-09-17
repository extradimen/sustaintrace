#!/usr/bin/env bash
set -u

pdf="data/raw/p13_staging/schneider-electric-2025-universal-registration-document.pdf"
root="artifacts/p13/mineru_targets"
log_root="artifacts/p13/mineru_logs"
config="$PWD/configs/parsers/p13-mineru-3.4.0-runtime.json"
pages=(148 149 150 152 153 213 315 333 334 339 340 344 353)

mkdir -p "$root" "$log_root"

for page in "${pages[@]}"; do
  tag=$(printf 'P13-SCHNEIDER-URD2025-p%04d' "$page")
  out="$root/$tag"
  md="$out/schneider-electric-2025-universal-registration-document/auto/schneider-electric-2025-universal-registration-document.md"
  middle="$out/schneider-electric-2025-universal-registration-document/auto/schneider-electric-2025-universal-registration-document_middle.json"
  if [[ -s "$md" && -s "$middle" ]]; then
    printf 'SKIP complete page %s\n' "$page"
    continue
  fi
  mkdir -p "$out"
  zero=$((page - 1))
  printf 'START page %s zero_based=%s\n' "$page" "$zero"
  if MINERU_TOOLS_CONFIG_JSON="$config" /opt/anaconda3/bin/magic-pdf -p "$pdf" -o "$out" -m auto -s "$zero" -e "$zero" >"$log_root/$tag.log" 2>&1 && [[ -s "$md" && -s "$middle" ]]; then
    printf 'DONE page %s\n' "$page"
  else
    code=$?
    if [[ "$code" -eq 0 ]]; then code=90; fi
    printf 'FAIL page %s exit=%s log=%s\n' "$page" "$code" "$log_root/$tag.log"
  fi
done
