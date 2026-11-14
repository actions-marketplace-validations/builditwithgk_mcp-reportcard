#!/usr/bin/env bash
# Assemble the static Hugging Face Space into a folder (default: space/_site).
# The page runs the stdlib-only core of mcp_reportcard in the browser via Pyodide.
# Run from the repo root:  bash space/build.sh [out_dir]
set -euo pipefail

OUT="${1:-space/_site}"
rm -rf "$OUT"
mkdir -p "$OUT/mcp_reportcard" "$OUT/samples"

cp space/index.html space/README.md "$OUT"/
for m in __init__ models loader tokens rules analyze report; do
  cp "src/mcp_reportcard/$m.py" "$OUT/mcp_reportcard/"
done
cp examples/bad_tools.json examples/good_tools.json "$OUT/samples/"
echo "Built $OUT"
