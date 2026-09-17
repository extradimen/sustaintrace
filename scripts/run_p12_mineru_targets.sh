#!/usr/bin/env bash
set -u

pdf="data/raw/p12_staging/volkswagen-group-annual-report-2025.pdf"
root="artifacts/p12/mineru_targets"
log_root="artifacts/p12/mineru_logs"
config="$PWD/configs/parsers/p12-mineru-3.4.0-runtime.json"
pages=(214 215 259 260 274 275 276 280 281 366 659 660 663)

mkdir -p "$root" "$log_root"

for page in "${pages[@]}"; do
  tag=$(printf 'P12-VOLKSWAGEN-AR2025-p%04d' "$page")
  out="$root/$tag"
  md="$out/volkswagen-group-annual-report-2025/auto/volkswagen-group-annual-report-2025.md"
  middle="$out/volkswagen-group-annual-report-2025/auto/volkswagen-group-annual-report-2025_middle.json"
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
