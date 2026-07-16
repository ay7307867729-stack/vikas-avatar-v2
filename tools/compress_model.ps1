# PowerShell script to compress a GLB using gltf-transform CLI

# Requires Node.js and npm. Install gltf-transform CLI globally:
# npm i -g @gltf-transform/cli

$input = "static/models/modelToUsed.glb"
$backup = "static/models/modelToUsed.bak.glb"
$dracoOut = "static/models/modelToUsed.draco.glb"
$out = "static/models/modelToUsed.compressed.glb"

if (-Not (Test-Path $input)) {
    Write-Error "Input file not found: $input"
    exit 1
}

Write-Output "Backing up original to $backup"
Copy-Item -Path $input -Destination $backup -Force

Write-Output "Running Draco compression (encoder-level 7)"
# Adjust encoder-level (1-10) for faster/slower and quality/size tradeoff
gltf-transform draco $input $dracoOut --encoder-level=7

Write-Output "Quantizing to reduce vertex precision"
# vertex-quantize values: 16 for positions, 12-14 for normals, 8-10 for texcoords
gltf-transform quantize $dracoOut $out --vertex-quantize=16 --texcoord-quantize=12

Write-Output "Compression complete. Output: $out"
Write-Output "Verify the model visually and compare to the backup before replacing the original."
