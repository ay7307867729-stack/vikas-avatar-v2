#!/usr/bin/env bash
# Bash script to compress a GLB using gltf-transform CLI
# Requires Node.js and npm. Install gltf-transform CLI globally:
# npm i -g @gltf-transform/cli

INPUT="static/models/modelToUsed.glb"
BACKUP="static/models/modelToUsed.bak.glb"
DRACO_OUT="static/models/modelToUsed.draco.glb"
OUT="static/models/modelToUsed.compressed.glb"

if [ ! -f "$INPUT" ]; then
  echo "Input file not found: $INPUT"
  exit 1
fi

echo "Backing up original to $BACKUP"
cp "$INPUT" "$BACKUP"

echo "Running Draco compression (encoder-level 7)"
# Adjust encoder-level (1-10) for faster/slower and quality/size tradeoff
gltf-transform draco "$INPUT" "$DRACO_OUT" --encoder-level=7

echo "Quantizing to reduce vertex precision"
# vertex-quantize values: 16 for positions, 12-14 for normals, 8-10 for texcoords
gltf-transform quantize "$DRACO_OUT" "$OUT" --vertex-quantize=16 --texcoord-quantize=12

echo "Compression complete. Output: $OUT"
echo "Verify the model visually and compare to the backup before replacing the original."
