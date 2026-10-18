# Geometry before finish

## Author an editable scene

Use scene-specific Blender/Python authoring for the native/GLB track. Keep shell, furniture and detail construction editable; retain the script, native master, named components, units and source camera. A procedural Three.js factory can be a separate implementation track, but do not claim that a Blender export fulfilled that factory's contract.

Create stable semantic component IDs on meshes and separate metadata for finish groups, lightmap atlas assignment and interactive parts. Identify curtain body/hem/hooks explicitly; a hem may have a different UV layout from the cloth it follows.

The actual entrypoint is `build_scene(context)` in the workspace, not an installed canned room. Use [scene contract](scene-contract.md), reusable `context.helpers` and the complete `examples/studio/build_scene.py` only as an explicitly independent mechanism example. Run `author_scene.py draft --workspace W --run-id form-r01 --width 1280 --samples 96`, open its actual `draft-source.png`, and use `render --view DECLARED_VIEW` for other poses. A new draft starts an authoring revision; rebuild dependent transport instead of exporting stale atlases.

## Required inspections

1. Room shell: wall/floor/ceiling coverage, real apertures, thickness and room-side normals; document unseen faces as authored.
2. Furniture: real seats/backs/legs/arms, plausible silhouettes and source-guided proportions; no photographic cards.
3. Soft forms: actual loft, tapered corners, irregular gathered fabric, seams/piping seated against the surface rather than hovering.
4. Table/chair contact: inspect world-space contact geometry and close views, not shadows alone. Do not delete a tiny visible part to conceal an export/bake problem.
5. Glazing: explicit geometry/thickness and declared refraction/shadow approximation; do not make opaque structures transparent merely to brighten a render.
6. Fine detail: handles, frame rails, hooks, hems, art and rug fringe receive geometry/material treatment appropriate to their actual footprint.
7. Intersections: inspect required views, support contacts and clearance. Named visual gaps remain failures even when a topology utility is clean.

## UV and identity invariants

- Author explicit material UV0 at a declared physical tile size.
- Add a distinct non-overlapping bake UV1; do not repurpose or overwrite UV0.
- Preserve geometry, UV and material identity outside the named repair scope.
- Test finish variants only on their declared component group, not every similarly named material.
- Keep rejected candidates and evidence. Regenerate downstream bakes/exports when geometry or material transport changes.

## Geometry-stage evidence

Include source/lateral/reverse actual renders, component inventory, units/coordinate conventions, contact/clearance findings and remaining authored assumptions. Native save success, object count and triangle count alone are not visual acceptance. Record the decision only after looking at the scene.
