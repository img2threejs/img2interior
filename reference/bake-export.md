# Calibrate → bake → probe → export

## Prerequisites

An actually rendered, editable native scene with finite physical meshes, semantic components, explicit metric UV0, source camera, authored world/lights and source-image aspect. Review camera/form/materials first. Use the pinned bpy environment and an explicit workspace/spec; imports never generate files in the installed plugin.

## Coordinate/color calibration, not a realism grade

```sh
"$BLENDER_PYTHON" "$SKILL_DIR/tools/author_scene.py" calibrate --workspace "$PWD" --run-id calibration-r01 --width 256 --samples 8
"$BLENDER_PYTHON" "$SKILL_DIR/tools/author_scene.py" material-regression --workspace "$PWD" --run-id packing-r01
```

`calibrate` renders and reimports an asymmetric UV1 chart, checks actual glTF texture coordinates/scene bounds/decoded pixels, and renders a real equirectangular EXR with emissive cardinal panels to verify probe orientation. Its `runtimeLightmap` section emits an additional child viewer workspace, actual asymmetric float EXR field, rotated UV1 PBR model and Cycles expected image. The runtime has zero specular, black probe/background, no sun and PI lightmap intensity; native expected evaluates albedo × field.

Register that child with `interior_project.py start --workspace CHILD --image EXPECTED_RENDER --source-kind render`, install the real viewer there, `npm ci`/build/serve, select source camera and capture the actual canvas at the same projection/aspect. Verify its drawing-buffer dimensions and real device pixel ratio, not just CSS width; compare against `runtimeLightmap.expectedRender` without image realignment. This exercises the real EXR row decoder, channel 1 and PI convention; native generation alone does not certify browser sampling. Keep global and clearly defined interior-region errors, capture settings and fixture limits. Do not alter row orientation merely because a room render looks dark.

`material-regression` uses real PNG/native/GLB files: save packed pixels, change external albedo, refresh, remove external source, reopen and compare actual pixels/UV0; export non-white weighted sheen and verify native restoration on successful and actual filesystem-failed exports. It also repeats atlas preparation and real GLB export, checking stable policy-addressable material names, retained artist roughness and unchanged UV0. It qualifies the exercised Blender 4.3 workaround, not untested exporters or material appearance.

## Production bake

```sh
"$BLENDER_PYTHON" "$SKILL_DIR/tools/author_scene.py" bake --workspace "$PWD" --run-id final-r01 --resolution 2048 --samples 64
```

The pipeline groups physical surfaces into architecture/textiles/furniture/garden/details, skips incompatible glass/bulbs, keeps UV0 and creates a separate `Lightmap` UV1. It checks finite/noncollapsed UVs and allocates chart gutters. Textile/garden atlases use twice the requested base resolution; choose a budget from actual footprint, not an unlabelled universal quality claim.

Subsequent bakes reuse prepared materials and their existing UV0 mapping nodes rather than growing material-name suffixes or copies. Preserve the reserved `InteriorBakeTarget` ownership node when editing prepared native materials; material policies address the actual stable exported names.

Profile a labelled low-resolution mechanism smoke before the final bake. A tiny mesh collapsing at a small atlas is a real UV-budget failure: increase that group's resolution; never remove the mesh, relax the pixel-area guard or present the smoke as final quality. `--atlas GROUP` saves that completed group's receipt and packed master independently, allowing different justified per-group budgets. Full 2K/4K CPU bakes can outlive a command runner's deadline; use an appropriate long-running job, retain receipts and inspect its actual completion before probing/exporting. A timed-out bake is not success.

For each group it actually performs:

1. Full diffuse direct+indirect lighting without albedo color, linear EXR evidence.
2. Object-normal-guided HDR OpenImageDenoise filtering of lighting only.
3. UV1 emission bake of original UV0 albedo, optional alpha, and full-light × albedo static portable PNG with the chosen display transform once.
4. A second diffuse pass with direct SUN disabled, then restore native SUN energy in `finally`.
5. Denoised linear SUN-free ambient EXR for runtime, with PI-compensated lightmap intensity in the manifest.

Bake receipts include groups/objects, resolutions/samples, actual statistics, denoiser, lighting model and elapsed time. OIDN failure is a real failure; do not substitute a fake noise-free atlas. UV1 baking must not move source sampling away from UV0.

`--atlas textiles` scopes a repair; retained groups preserve old transport approximations. A globally changed layout/light/reflectance requires full regeneration. Do not call a partial bake a globally current physical GI solution.

## Packed image repair and probe freshness

```sh
"$BLENDER_PYTHON" "$SKILL_DIR/tools/author_scene.py" refresh-material --workspace "$PWD" --run-id material-r02 --image public/assets/interior/curtain-basecolor.png --image public/assets/interior/curtain-roughness.png
"$BLENDER_PYTHON" "$SKILL_DIR/tools/author_scene.py" bake --workspace "$PWD" --run-id material-r02 --resolution 2048 --samples 64
"$BLENDER_PYTHON" "$SKILL_DIR/tools/author_scene.py" probe --workspace "$PWD" --run-id material-r02 --width 1024 --samples 96
```

Use actual named used maps, not showcase filenames for another scene. Refresh unpacks only selected stale images, reloads disk pixels, repacks and preserves topology/UV; it invalidates atlases and the authoring revision. Draft also starts a new revision. Probe renders the current scene at the declared indoor pose with the measured native/glTF orientation and records revision/pose/actual EXR hash. Export rejects an old/mutated probe even when a file of that name exists. Out-of-band Blender edits still require explicit dependent regeneration; this is not a sandbox or universal scene-diff engine.

## Export distinct products

```sh
"$BLENDER_PYTHON" "$SKILL_DIR/tools/author_scene.py" export --workspace "$PWD" --run-id final-r01
```

Export checks complete current bake inventory/model and clean required atlases. It reconstructs authoring receipt from the reopened master rather than requiring a prior run's evidence folder. Source dimensions, view names, room bounds, probe/background, optional sun, finishes and credit derive from this scene/spec.

- `room-master.blend`: actual packed editable scene, geometry, UV0/UV1, PBR and lights. This is not a GLB.
- `room-runtime.glb`: real PBR with UV0/UV1 and semantic/interaction extras; EXR atlases/probe and optional HDR background remain required sidecars.
- `room-portable.glb`: independent embedded full-static diffuse appearance, `KHR_materials_unlit` sampling UV1; not a browser shader/physics/dye-state export.
- `manifest.json`: schema-2 runtime paths/camera/bounds/lightmaps/lighting/variants/limits and receipt-derived live API credit.

Export-only tangent-cap triangulation, native thin-pane output substitution and constant weighted-sheen tint conversion are temporary and restored even on failure. Portable material swaps also restore native slots in `finally`. Native GI/probe remain static as cloth/finishes change; glass transmission is a declared approximation, not real-time caustics.

## Exit criteria

Open the source/lateral/material/contact renders and actual viewer. Run current material/delivery audits, Khronos validation and independent `inspect_scene.py master|portable`; compare source and close views separately. Keep reports/hashes/versioned evidence, packing/color-transform facts and static/runtime limits. A zero exit code, triangle count or calibration MAE is not visual acceptance.
