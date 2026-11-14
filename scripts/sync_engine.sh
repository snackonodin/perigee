#!/usr/bin/env bash
# Copy the read-only Context Engine from the separate waiwai1 repo into deploy/vendor/engine/
# so a cloud build (which cannot see waiwai1/) has it. Byte-identical copies + sha256 list.
# Run after any engine change, then commit deploy/vendor/engine/.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO/waiwai1/engine"; DST="$REPO/deploy/vendor/engine"
mkdir -p "$DST"
for f in api.py motion.py sleep_scorer.py; do cp "$SRC/$f" "$DST/$f"; done
printf '"""Vendored Context Engine (read-only copy of waiwai1/engine). See PROVENANCE.md."""\n' > "$DST/__init__.py"
rev="$(git -C "$REPO/waiwai1" rev-parse --short HEAD 2>/dev/null || echo unknown)"
{
  echo "# Provenance: Context Engine copy for deployment"
  echo
  echo "Source: waiwai1/engine at waiwai1 commit \`$rev\` (copied $(date -u +%Y-%m-%dT%H:%MZ))."
  echo "Do not edit here: the engine is read-only; change waiwai1 and re-run scripts/sync_engine.sh."
  echo
  echo "| File | sha256 |"; echo "|---|---|"
  for f in api.py motion.py sleep_scorer.py; do echo "| \`$f\` | \`$(shasum -a 256 "$DST/$f" | cut -d' ' -f1)\` |"; done
} > "$DST/PROVENANCE.md"
echo "synced engine @ $rev into deploy/vendor/engine"
