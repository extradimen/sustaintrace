#!/usr/bin/env bash
set -u

pdf="data/raw/p12_staging/volkswagen-group-annual-report-2025.pdf"
root="artifacts/p12/native_pdf_targets"
pages=(214 215 259 260 274 275 276 280 281 366 659 660 663)

mkdir -p "$root"
for page in "${pages[@]}"; do
  out=$(printf '%s/P12-VOLKSWAGEN-AR2025-p%04d.txt' "$root" "$page")
  if [[ -s "$out" ]]; then
    printf 'SKIP complete page %s\n' "$page"
    continue
  fi
  tmp="$out.partial"
  if pdftotext -f "$page" -l "$page" -layout -enc UTF-8 "$pdf" "$tmp" && [[ -s "$tmp" ]]; then
    mv "$tmp" "$out"
    printf 'DONE page %s\n' "$page"
  else
    code=$?
    printf 'FAIL page %s exit=%s partial=%s\n' "$page" "$code" "$tmp"
  fi
done
