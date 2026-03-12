#!/bin/bash
set -e

# ─── Ernos 3.0 — Build Secured Distribution Image ───
# Layers: Prompt Encryption (AES-256) → Bytecode Compilation → Source Deletion

TAG="${1:-ernos:latest}"

echo "═══════════════════════════════════════"
echo "  Building Ernos 3.0 Docker Image"
echo "  Tag: $TAG"
echo "  Security: AES-256 prompts + bytecode"
echo "═══════════════════════════════════════"

# ── Build the secured image ──
docker build -t "$TAG" .

# ── Verify security layers ──
echo ""
echo "🔍 Verifying source protection..."

# Check for .py files (should be zero or near-zero)
PY_FILES=$(docker run --rm --entrypoint /bin/bash "$TAG" -c "find /app/src /app/config -name '*.py' 2>/dev/null | wc -l" | tr -d ' ')
if [ "$PY_FILES" -gt 0 ]; then
    echo "ℹ️  Found $PY_FILES .py files (JS bridge stubs — expected)"
else
    echo "✅ No .py source files — only compiled bytecode."
fi

# Check for plaintext prompts (should all be .enc)
TXT_FILES=$(docker run --rm --entrypoint /bin/bash "$TAG" -c "find /app/src/prompts -name '*.txt' 2>/dev/null | wc -l" | tr -d ' ')
ENC_FILES=$(docker run --rm --entrypoint /bin/bash "$TAG" -c "find /app/src/prompts -name '*.enc' 2>/dev/null | wc -l" | tr -d ' ')
if [ "$TXT_FILES" -gt 0 ]; then
    echo "⚠️  WARNING: Found $TXT_FILES plaintext .txt prompt files!"
else
    echo "✅ No plaintext prompts — $ENC_FILES encrypted .enc files found."
fi

# Show image size
SIZE=$(docker image inspect "$TAG" --format='{{.Size}}' | numfmt --to=iec 2>/dev/null || docker image inspect "$TAG" --format='{{.Size}}')
echo "📦 Image size: $SIZE"

echo ""
echo "✅ Build complete: $TAG"
echo ""
echo "To run:"
echo "  docker run $TAG"
echo ""
echo "To push to a registry:"
echo "  docker tag $TAG your-registry.com/ernos:latest"
echo "  docker push your-registry.com/ernos:latest"
