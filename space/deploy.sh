#!/usr/bin/env bash
# Deploy the web demo to the Hugging Face Space builditwithgk/mcp-doctor.
# Needs: `hf auth login` done once. Run from the repo root:  bash space/deploy.sh
set -euo pipefail

SPACE="${SPACE:-builditwithgk/mcp-doctor}"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

cp space/Dockerfile space/README.md "$STAGE"/
cp -r src examples web "$STAGE"/
find "$STAGE" -name "__pycache__" -type d -prune -exec rm -rf {} +

hf repo create "$SPACE" --repo-type space --space-sdk docker --exist-ok
hf upload "$SPACE" "$STAGE" . --repo-type space --commit-message "Deploy from $(git rev-parse --short HEAD)"
echo "Deployed: https://huggingface.co/spaces/$SPACE"
