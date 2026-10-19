# Explicit Oak/Linen reproduction, never an arbitrary-room fallback

The recipe packages the actual scene-specific authoring from the authorized synthetic design study: room/glazing, sofa and skewed lofted pillows/BVH-seated seams, authored hairpin table/lounge chair, rug/fringe, lamps/books/vessels, two interactive rail curtains and local garden. Generic tools remain independent; case assembly lives in `recipes/oak-linen/build_scene.py`.

## Required caller source

The original image is not bundled. Supply its exact authorized bytes, 2752×1536 PNG:

`95eb31d840165964deac849813dc77ad18bad71f1df90770bff1f7b4a5fb666b`

It is a synthetic design reference, not an independently measured photograph. The installer, material crop recipe and case builder guard the actual source hash. A different image requires a newly authored scene/spec/surfaces, not deleting guards or silently keeping this room.

## Cold workspace commands

```sh
python3 "$SKILL_DIR/tools/interior_project.py" start --workspace "$PWD" --image "$IMAGE" --source-kind synthetic-design-reference
python3 "$SKILL_DIR/tools/interior_project.py" use-recipe --workspace "$PWD" --recipe oak-linen
python3 "$SKILL_DIR/tools/polyhaven.py" fetch --workspace "$PWD" --selection resource-selection.json
"$IMAGE_PYTHON" "$SKILL_DIR/tools/prepare_surfaces.py" --workspace "$PWD" --recipe surfaces.json
"$BLENDER_PYTHON" "$SKILL_DIR/tools/author_scene.py" draft --workspace "$PWD" --run-id case-r01 --width 1280 --samples 96
"$BLENDER_PYTHON" "$SKILL_DIR/tools/author_scene.py" bake --workspace "$PWD" --run-id case-r01 --resolution 2048 --samples 64
"$BLENDER_PYTHON" "$SKILL_DIR/tools/author_scene.py" probe --workspace "$PWD" --run-id case-r01 --width 1024 --samples 96
"$BLENDER_PYTHON" "$SKILL_DIR/tools/author_scene.py" export --workspace "$PWD" --run-id case-r01
python3 "$SKILL_DIR/tools/interior_project.py" install-viewer --workspace "$PWD"
npm ci
npm run build
```

Prepare the isolated environments and initialize the agent-authored intake/reviews as in the [runbook](production-runbook.md). Run real calibration, visual repair, browser interactions, independent native/portable reopening and current audits before delivery. Recipe installation does not accept any stage.

## What is reusable versus case-specific

| Reusable production mechanism | Case-only choices |
|---|---|
| Live Poly Haven discovery/descriptors/dependency acquisition/integrity | Exact five models, five scans and two HDRIs selected in this study; not all downloaded models were instantiated. |
| Recipe-driven linear dye/roughness/crop/metric yarn tools | Walnut/chair/floor/plaster/linen/leather dyes, 2k marble source crop, artwork pixel rectangle and rug weave settings. |
| Actual Blender geometry/PBR/UV helpers, two-pass bakes/OIDN/probe/export | This room's shell/geometry/camera, physical proportions, hidden extension and lighting estimates. |
| Manifest-driven Three lighting, navigation and point-bound cloth | Two explicit case rails, sofa finish group and its three colors. |
| Native/runtime/portable consumer checks and causal repair loop | Historical counts, hashes, close-up errors, performance and visual decisions. |

Downloaded asset bytes may change upstream; current verified acquisition receipts describe this run. The large original images/models/maps/master/GLBs, credentials, cached catalog and historical screenshots are not part of the installable source ZIP. The recipe does not read an absolute source-project path, old outputs or a private machine environment.

## Interpretation and known limits

Camera, metre scale, hidden surfaces, reflectance, dyes and scan footprints remain authored estimates. The source-specific artwork crop is an explicitly labeled artwork texture, not permission to turn furniture/room structure into photo cards. Native thin-pane shadows and runtime two-interface sun transmission are approximations; open-curtain GI/probe and portable appearance remain static.

Historical showcase evidence is summarized in [lessons](showcase-lessons.md). Keep current smoke evidence with the authored project's delivery. Do not report a small low-sample mechanism smoke as a fresh full-quality photorealism or real-phone acceptance run.
