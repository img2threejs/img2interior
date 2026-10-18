# Resource discovery, acquisition and surface preparation

## Search suitable assets, not just available assets

Use free public CC0 resources within the assignment's authority. Paid generation, uploading the user's image, restricted models and public deployment need separate authorization. Procedurally authored geometry/PBR is valid when it matches the brief; do not substitute a visually wrong scan merely because it downloads.

```sh
python3 "$SKILL_DIR/tools/polyhaven.py" search --workspace "$PWD" --type models --query 'lounge chair' --limit 5
python3 "$SKILL_DIR/tools/polyhaven.py" search --workspace "$PWD" --type textures --query 'linen fabric' --limit 5
python3 "$SKILL_DIR/tools/polyhaven.py" info --workspace "$PWD" --id rough_linen
python3 "$SKILL_DIR/tools/polyhaven.py" files --workspace "$PWD" --id rough_linen
```

The live [Poly Haven API](https://api.polyhaven.com/api-docs/swagger.json) provides ranked metadata search, asset info and file descriptors. Inspect candidate imagery or import/render candidate geometry. Rank/similarity is not silhouette, BRDF or source-image fit. Record selected, rejected and actually instantiated assets separately.

Author `resource-selection.json` with integer `schemaVersion:1`, a nonempty `reason` and arrays `models`, `textures`, `hdris` (empty arrays allowed). Each selected entry declares `id`, `resolution`, `format`, `purpose`:

```json
{"schemaVersion":1,"reason":"Observed textile needs a woven scan","models":[],"textures":[{"id":"rough_linen","resolution":"2k","format":"jpg","purpose":"Curtain UV0 weave"}],"hdris":[]}
```

```sh
python3 "$SKILL_DIR/tools/polyhaven.py" fetch --workspace "$PWD" --selection resource-selection.json
```

Models use `gltf` and include every published dependency with its original relative layout; textures require actual `Diffuse`, `nor_gl` and `Rough` descriptors mapped to `color`, `normal`, `roughness`; HDRIs use `hdr` or `exr`. Inspect `files` before choosing unsupported resolutions/formats. Missing channels fail; they are not silently synthesized.

Downloads live under `resources/polyhaven/<id>/`. The receipt `.img2/artifacts/interior/resources.json` records selection, asset metadata, local model/map/HDR paths, `modelIncludes`, publisher URL/size/MD5 and actual SHA256. Same-size cached files are still MD5 checked. Paths, glTF URIs and HTTPS redirect hosts are confined; reads/transfers are bounded. Failure does not mean a partially downloaded asset is usable.

The tool visibly credits **Powered by Poly Haven**. Downloaded assets are [CC0](https://polyhaven.com/license), while use of the live service has separate [API terms](https://github.com/Poly-Haven/Public-API/blob/master/ToS.md). The actual API client identifies itself; no API server source or API key is bundled. A balance/CC0 license is not paid-generation permission.

## Prepare actual PBR inputs

Run image tools in a separate NumPy/Pillow environment, not the pinned bpy environment. Author `surfaces.json`; source-specific crop coordinates require actual observation and should pin the intended reference hash.

```sh
"$IMAGE_PYTHON" "$SKILL_DIR/tools/prepare_surfaces.py" --workspace "$PWD" --recipe surfaces.json
```

Recipe schema: `schemaVersion:1`, optional `resourceManifest` (default current private resource receipt), `spec` (default `scene-spec.json`), optional `referenceSha256`, and nonempty `operations`. Each operation has a unique `id`, `op`, and output PNG under `public/assets/interior/`. Inputs/recipes/downloads cannot be outputs.

Input alternatives: `{"texture":"rough_linen","channel":"color"}`, `{"model":"coffee_table_round_01","include":"textures/coffee_table_round_01_diff_2k.jpg"}`, `{"reference":true}`, or `{"path":"inputs/scan.png"}`. Downloaded input hashes are checked against the resource receipt. Reference resolves from `spec.source`, including the actual extension; decoded images honor EXIF orientation.

| Operation | Parameters and actual work |
|---|---|
| `dye` | Decode sRGB → linear luminance; normalize by scan median; clamp `bounds`, optional `exponent`, `strength`, `normalizeMean`, `blur` and `crop`; multiply explicit `dye:{space:"srgb255" or "linear",value:[r,g,b]}`; encode sRGB. |
| `roughness` | Decode grayscale; `offset + scale * (scan - median)` for `center:"median"`, or no subtraction for `"zero"`; clamp `bounds` in 0..1. |
| `crop` | Explicit integer `[left,top,right,bottom]`; reject out-of-bounds rectangles instead of padding an invented surface. |
| `woven` | Deterministic periodic crossing-yarn field from `resolution`, even `yarns`, `tileMetres`, `seed`, dye and optional physical height/noise/roughness parameters; `outputs:{basecolor,normal,roughness}`; metric derivatives yield OpenGL +Y normals. |

```json
{"schemaVersion":1,"operations":[{"id":"cloth-dye","op":"dye","input":{"texture":"rough_linen","channel":"color"},"dye":{"space":"srgb255","value":[210,206,202]},"bounds":[0.78,1.15],"strength":0.45,"output":"public/assets/interior/linen-neutral.png"}]}
```

`.img2/artifacts/interior/surfaces.json` records recipe/input/output hashes, operation parameters, decoded pixel dimensions/mode/min/max/mean/std, and actual NumPy/Pillow versions. Woven receipts also declare tile/pitch/normal convention. These are authored transformations, not recovered reflectance or visual acceptance.

## Exit criteria

Every used asset has a purpose, safe local dependencies and recorded rights/provenance. Required maps exist and are actually bound by the native material factory. The agent has inspected material identity, physical tile scale, decoded roughness and real frontal/grazing views. Downloads, dictionary entries and a high roughness scalar alone are insufficient.
