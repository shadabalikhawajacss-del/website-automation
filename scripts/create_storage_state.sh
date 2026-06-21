#!/usr/bin/env bash
set -euo pipefail

: "${RTBDI_BASE_URL:=https://www.myrtpos.com/newbdi/index.fwx}"
: "${RTBDI_STORAGE_STATE:=./storage-state.json}"

if [[ -z "${RTBDI_USERNAME:-}" || -z "${RTBDI_PASSWORD:-}" ]]; then
  echo "RTBDI_USERNAME and RTBDI_PASSWORD must be set" >&2
  exit 1
fi

RTBDI_BASE_URL="$RTBDI_BASE_URL" \
RTBDI_USERNAME="$RTBDI_USERNAME" \
RTBDI_PASSWORD="$RTBDI_PASSWORD" \
python -m rtbdi_assistant.cli login-session --storage-state "$RTBDI_STORAGE_STATE"

echo "Saved RT BDI storage state to $RTBDI_STORAGE_STATE"
