#!/usr/bin/env bash
# Compiles lib/drafts.ts to CommonJS and runs the invariant checks in check-drafts.cjs.
# Asserts that drafts never invent employers, awards, work authorization or stipend expectations.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="$(mktemp -d)"
npx tsc lib/drafts.ts --outDir "$OUT" --module commonjs --target ES2020 --skipLibCheck
cp scripts/check-drafts.cjs "$OUT/"
node "$OUT/check-drafts.cjs"
