#!/usr/bin/env bash
set -u

pdf="data/raw/p13_staging/schneider-electric-2025-universal-registration-document.pdf"
root="artifacts/p13/native_pdf_targets"
pages=(148 149 150 152 153 213 315 333 334 339 340 344 353)

mkdir -p "$root"
for page in "${pages[@]}"; do
  out=$(printf '%s/P13-SCHNEIDER-URD2025-p%04d.txt' "$root" "$page")
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
