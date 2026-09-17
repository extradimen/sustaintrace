#!/usr/bin/env bash
set -u

BASE="/Users/michaelwang/.cache/huggingface/hub/models--opendatalab--PDF-Extract-Kit-1.0"
REV="ed6b654c018d742e65a17671e379c5e6ecc87ec9"
SNAP="$BASE/snapshots/$REV/models/OCR/paddleocr_torch"
LOG_DIR="/Users/michaelwang/Documents/ChatGPT/EdgeModel&ESG/artifacts/downloads"
LOG="$LOG_DIR/mineru_ocr_batch.log"

mkdir -p "$SNAP" "$LOG_DIR"

FILES=(
  "korean_PP-OCRv5_rec_infer.pth|29495617|405b72b79a652a87c49d92700d5677e82375c5f6e242b6f54e5faf2264f8aeb5"
  "latin_PP-OCRv5_rec_infer.pth|24118861|eeb50a7998a44ac6f3a03855774d5c12aeca93e2209412679879d2bf604a8fd6"
  "seal_PP-OCRv4_det_infer.pth|14506268|a7777ca66448ab90948ce5a3257e4c959d6eacf0489fbadd5133dbe8f89662ae"
  "seal_PP-OCRv4_det_server_infer.pth|114030092|283d716bdd93d011edca4563d218a767b273c47bf9c32cb3e8a0baf5b12c8242"
  "ta_PP-OCRv5_rec_infer.pth|23966667|577d0530f55e3856064fb31e8bcd3ca4714151bacd93696a1f8dda9c06e4bdb3"
  "te_PP-OCRv5_rec_infer.pth|23977665|85a7d6ce53591c288da965559dd1cebd12e26294554a6e72641d82070acdd5b9"
  "th_PP-OCRv5_rec_infer.pth|23971991|9830b0c1532620851b6cdcd6bb2f4abed7d84ea70112497cc7d1e86a5885fdc6"
)

stamp() { date '+%Y-%m-%dT%H:%M:%S%z'; }
log() { printf '%s %s\n' "$(stamp)" "$*" >> "$LOG"; }

download_one() {
  local entry="$1"
  local name expected sha blob partial url before after rc actual_sha
  IFS='|' read -r name expected sha <<< "$entry"
  blob="$BASE/blobs/$sha"
  partial="$blob.incomplete"
  url="https://huggingface.co/opendatalab/PDF-Extract-Kit-1.0/resolve/$REV/models/OCR/paddleocr_torch/$name"

  if [[ -f "$blob" ]] && [[ "$(stat -f '%z' "$blob")" == "$expected" ]] && [[ "$(shasum -a 256 "$blob" | awk '{print $1}')" == "$sha" ]]; then
    ln -sfn "../../../../../blobs/$sha" "$SNAP/$name"
    log "SKIP verified $name bytes=$expected sha256=$sha"
    return 0
  fi

  while :; do
    before=0
    [[ -f "$partial" ]] && before="$(stat -f '%z' "$partial")"
    log "START $name offset=$before expected=$expected"
    curl -L --fail -C - -o "$partial" "$url" >> "$LOG" 2>&1
    rc=$?
    after=0
    [[ -f "$partial" ]] && after="$(stat -f '%z' "$partial")"
    log "TRANSFER_END $name rc=$rc before=$before after=$after"

    if [[ "$after" -eq "$expected" ]]; then
      actual_sha="$(shasum -a 256 "$partial" | awk '{print $1}')"
      if [[ "$actual_sha" == "$sha" ]]; then
        mv "$partial" "$blob"
        ln -sfn "../../../../../blobs/$sha" "$SNAP/$name"
        log "VERIFIED $name bytes=$expected sha256=$sha"
        break
      fi
      log "FATAL hash_mismatch $name expected=$sha actual=$actual_sha"
      return 2
    fi

    if [[ "$after" -lt "$before" ]]; then
      log "FATAL size_regression $name before=$before after=$after"
      return 3
    fi
    if [[ "$after" -gt "$expected" ]]; then
      log "FATAL oversized $name expected=$expected actual=$after"
      return 4
    fi
    sleep 2
  done
}

worker() {
  local worker_id="$1"
  local i
  for ((i=worker_id; i<${#FILES[@]}; i+=3)); do
    download_one "${FILES[$i]}" || return $?
  done
}

pids=()
for worker_id in 0 1 2; do
  worker "$worker_id" &
  pids+=("$!")
done

status=0
for pid in "${pids[@]}"; do
  wait "$pid" || status=$?
done

if [[ "$status" -ne 0 ]]; then
  log "FAILED one_or_more_workers status=$status"
  exit "$status"
fi

log "COMPLETE all_remaining_ocr"
