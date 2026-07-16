Compression options for `static/models/modelToUsed.glb`

Recommended: use `gltf-transform` CLI (fast, reliable, supports Draco + quantization).

1) Install prerequisites
- Install Node.js and npm: https://nodejs.org/
- Install `gltf-transform` CLI:

```bash
npm i -g @gltf-transform/cli
```

2) Run the provided script (PowerShell on Windows):

```powershell
cd "c:\Users\hp\OneDrive\Desktop\vikas avtar"
.\tools\compress_model.ps1
```

Or on macOS / Linux:

```bash
cd "/path/to/workspace"
./tools/compress_model.sh
```

3) What the scripts do
- Back up the original file to `static/models/modelToUsed.bak.glb`.
- Run `draco` compression to reduce mesh size.
- Quantize vertex attributes to further reduce size.
- Produce `static/models/modelToUsed.compressed.glb`.

4) Tuning
- Change `--encoder-level` (1-10) for stronger compression.
- Change `--vertex-quantize`/`--texcoord-quantize` numbers to trade quality vs size.

5) Alternatives
- `gltfpack` (https://github.com/zeux/meshoptimizer) — very effective but requires building/installing the binary.
- Blender: manually re-export with lower texture sizes or simplified mesh.

6) Safety
- Always verify the compressed model visually before replacing the original.
- If textures look washed out, consider lowering texture quantization or re-embedding high-quality JPEG/PNG.
