# Intake and camera

## 1. Establish source authority

Inspect the actual reference before modeling. Record whether it is a photo, synthetic design reference, render or floorplan; who authorized use; immutable SHA256; physical scale basis; critical components; and unknowns. An authorized synthetic design is not an independent observation photograph.

Create the intake JSON described in [tool inputs](tool-inputs.md). Use the showcase example only with that showcase source. `init` validates and snapshots the declaration; it cannot verify a permission claim or infer measurements. Review it explicitly at stage `intake`, citing `.img2/artifacts/interior/intake.json` and any source-analysis evidence.

Start with `interior_project.py start --workspace W --image IMAGE --source-kind KIND`; this pins bytes/display geometry, not pixel meaning or reviewer approval. The agent reads the pixels and [technical references](reference-analysis.md), then authors intake/spec/builder itself. Use [production runbook](production-runbook.md) for executable setup; do not ask the user to prepare those JSON files.

Record image bounds and normalized visible anchors for actual room planes/apertures/dominant objects, their framing and negative space; do not require a sofa or other case furniture absent from this image. Identify crops/occlusions. Distinguish observed outline, guessed depth and design choices. Ask only if missing information creates a materially different required output; otherwise state the conservative authored assumption.

## 2. Calibrate composition before detail

1. Choose metre units and author a named coordinate-system conversion (Blender Z-up; glTF/Three.js Y-up).
2. Block out room shell, apertures and dominant furniture using genuine volumes.
3. Match source camera orientation, field of view, horizon and framing with a real render at the source aspect ratio.
4. Compare silhouette, component proportions, placement and negative space before adding texture/lighting complexity.
5. Capture source and sufficient lateral/reverse inspections to expose hidden/contact failures. View names/count follow the authored scene; do not claim hidden-view accuracy from one input.
6. Record camera world matrix/pose, target, FOV, near/far, viewport and canvas bounds with the screenshots.

The user rejecting a form is a real failure even if a GLB validator passed. Preserve the rejected capture and causal repair, then repeat the camera/geometry stage. Do not use material polish to conceal a wrong table, seat front, pillow outline or chair silhouette.

## Camera import and runtime safety

Imported glTF cameras may use quaternion rotation. Switching only Euler values can leave the old orientation active. Set the intended rotation representation explicitly and inspect forward/target alignment, parent transforms and actual output footprint.

Constrain both eye and target against the room shell after every controls update, including updates below an event emitter's epsilon. Exercise orbit, pan, dolly/zoom, keyboard and reset. Camera proximity limits are authored safety policy, not physical collision certification.

## Evidence and stage decisions

- `intake`: pinned intake snapshot, source-analysis/permission/uncertainty notes.
- `camera`: actual coarse render(s), camera/projection receipt, named composition decisions and remaining uncertainty.
- Record reviewer identity and explicit acceptance only after observing those artifacts.
- Capture inside the existing canvas viewport. In the showcase, a beyond-viewport capture changed canvas width/aspect while camera position stayed fixed; do not relax camera assertions to cover a capture-induced layout mutation.
