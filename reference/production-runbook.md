# One assignment: image to working interior

The image-capable agent executes this runbook, authors its inputs/code and repairs observed failures. The user need not supply a scene JSON, resource manifest, camera or per-step approvals. This is not a universal neural recovery model; visual interpretation and scene-specific code are agent work.

## 1. Prepare the actual workspace

Keep `SKILL_DIR` pointed at the installed plugin, `PWD` at the authored project, and `IMAGE` at the supplied image. Observe the source kind before choosing `SOURCE_KIND`. Preserve unrelated files and existing review history.

```sh
python3 "$SKILL_DIR/tools/interior_project.py" start --workspace "$PWD" --image "$IMAGE" --source-kind "$SOURCE_KIND"
```

Start preserves bytes and records header/display size, hash and authority. It may adopt an identical existing reference but never overwrite a different one. Read the actual source/reference pages and author the intake, [scene specification/builder](scene-contract.md), visible anchors, uncertainties, output budget and intended material policy. Only the exact source-pinned case can use [Oak/Linen reproduction](oak-linen-recipe.md).

## 2. Prepare project-local environments

Use existing compatible tools if available; otherwise install locally. For example, with `uv` already available:

```sh
uv venv --python 3.11 .venv-blender
uv pip install --python .venv-blender/bin/python -r "$SKILL_DIR/requirements-authoring.txt"
uv venv --python 3.12 .venv-images
uv pip install --python .venv-images/bin/python -r "$SKILL_DIR/requirements-surfaces.txt"
export BLENDER_PYTHON="$PWD/.venv-blender/bin/python"
export IMG2_BLENDER_PYTHON="$BLENDER_PYTHON"
export IMAGE_PYTHON="$PWD/.venv-images/bin/python"
python3 "$SKILL_DIR/tools/interior_project.py" preflight --workspace "$PWD" --blender-python "$BLENDER_PYTHON"
```

`python3.11 -m venv` / pip is also usable when that interpreter is installed; Windows venv executables use `Scripts/python.exe`. Do not claim untested OS/wheel support. bpy 4.3.0 and NumPy 1.26.4 are isolated from image-tools NumPy/Pillow. Preflight performs real executable/import probes, not installs or visual checks.

## 3. Pin intake and establish composition

```sh
python3 "$SKILL_DIR/tools/interior_workflow.py" init --workspace "$PWD" --image "$IMAGE" --intake interior-intake.json
python3 "$SKILL_DIR/tools/interior_workflow.py" next --workspace "$PWD"
"$BLENDER_PYTHON" "$SKILL_DIR/tools/author_scene.py" draft --workspace "$PWD" --spec scene-spec.json --run-id camera-r01 --width 640 --samples 16
"$BLENDER_PYTHON" "$SKILL_DIR/tools/author_scene.py" render --workspace "$PWD" --run-id camera-r01 --view left --width 640 --samples 16
"$IMAGE_PYTHON" "$SKILL_DIR/tools/compare_views.py" --workspace "$PWD" --run-id camera-r01 --render .img2/artifacts/interior/production/camera-r01/draft-source.png
```

Use a view actually declared in the spec, not a mandatory `left`. Open renders/contact sheet; compare framing, source aspect, silhouettes, placement and negative space. Record intake/camera only after inspection. Contact sheets preserve framing/labels and optional normalized `--roi L T R B`; they do not compute likeness or assume pixel alignment.

## 4. Acquire assets, build geometry, prepare PBR

Follow [resources](resources.md), [geometry](geometry.md) and [materials](materials.md). Search live candidates, inspect actual shape/maps, author selection/purpose and fetch verified CC0 files. Write scene-specific geometry and surfaces; run real preparation where needed.

```sh
python3 "$SKILL_DIR/tools/polyhaven.py" fetch --workspace "$PWD" --selection resource-selection.json
"$IMAGE_PYTHON" "$SKILL_DIR/tools/prepare_surfaces.py" --workspace "$PWD" --recipe surfaces.json
"$BLENDER_PYTHON" "$SKILL_DIR/tools/author_scene.py" draft --workspace "$PWD" --run-id form-r01 --width 1280 --samples 96
```

Inspect source/lateral/reverse/contact and fixed frontal/grazing material views. A geometry correction changes the builder and requires a new draft. To replace an already-used image map, update only its intended derivative, then `refresh-material --image public/assets/interior/MAP.png`; this reloads packed bytes, preserves geometry/UVs and invalidates transport. Other material graph changes require rebuilding or an explicit reviewed native edit, not pretending a pixel reload changed a shader graph.

## 5. Render, reject and causally repair

A rejection is ground truth. Name the defect, preserve the failing capture, run workflow `revise --from` the earliest affected stage, change actual geometry/material/camera/light/input code, regenerate dependencies and observe new captures. Use new round IDs; do not overwrite accepted evidence. Do not change tolerance/exposure/claims to disguise an unresolved shape or fabric problem.

Native reports/renders live under `.img2/artifacts/interior/production/RUN/`. Same stage/view/atlas evidence is not reusable within a run; choose another run ID after a failed invocation or revision. Current `.blend`/GLB/maps are mutable products; early approvals should cite immutable views/inventory/receipts, not product bytes that a later bake/export legitimately rewrites.

## 6. Calibrate and produce final native/runtime/portable assets

Follow [bake/export](bake-export.md), including the actual native/EXR/browser fixture. Provisional low-cost bakes can support material inspection; final lighting approval needs the chosen production settings and visible checks.

```sh
"$BLENDER_PYTHON" "$SKILL_DIR/tools/author_scene.py" bake --workspace "$PWD" --run-id final-r01 --resolution 2048 --samples 64
"$BLENDER_PYTHON" "$SKILL_DIR/tools/author_scene.py" probe --workspace "$PWD" --run-id final-r01 --width 1024 --samples 96
"$BLENDER_PYTHON" "$SKILL_DIR/tools/author_scene.py" export --workspace "$PWD" --run-id final-r01
```

Dynamic SUN is not baked into runtime ambient atlases. Portable uses separately baked full-static diffuse appearance; native preserves editable PBR. Refreshing pixels/geometry requires current bakes and probe; old probe existence is insufficient. Inspect actual outputs before accepting lighting.

## 7. Install and exercise the actual viewer

```sh
python3 "$SKILL_DIR/tools/interior_project.py" install-viewer --workspace "$PWD"
npm ci
npm run build
npm run preview -- --host 127.0.0.1 --port 5179
```

Keep the server running using the agent host's managed service mechanism. Open a real browser tab, follow [viewer integration](viewer-integration.md) and [interaction](interaction.md), capture desktop/narrow and actual input/lifecycle results, then close the tab. Test production preview, not just a source-code test. No deployment permission is implied.

## 8. Independently inspect, audit and hand off

```sh
"$BLENDER_PYTHON" "$SKILL_DIR/tools/inspect_scene.py" master --workspace "$PWD" --run-id delivery-r01 --width 1280 --samples 64
"$BLENDER_PYTHON" "$SKILL_DIR/tools/inspect_scene.py" portable --workspace "$PWD" --run-id delivery-r01 --width 1280 --samples 64
node "$SKILL_DIR/tools/validate_scene.mjs" --workspace "$PWD" --asset public/assets/interior/room-runtime.glb --run-id delivery-r01
node "$SKILL_DIR/tools/validate_scene.mjs" --workspace "$PWD" --asset public/assets/interior/room-portable.glb --run-id delivery-r01
python3 "$SKILL_DIR/tools/audit_materials.py" --workspace "$PWD" --glb public/assets/interior/room-runtime.glb --policy material-policy.json
python3 "$SKILL_DIR/tools/interior_project.py" delivery-contract --workspace "$PWD"
python3 "$SKILL_DIR/tools/audit_delivery.py" --workspace "$PWD" --contract .img2/artifacts/interior/delivery-contract.json
```

Freeze changing audit receipts with `interior_project.py snapshot`, cite actual consumer/render/input evidence, complete all eight stage attestations in order and run `run_gates.py --plugin-dir "$SKILL_DIR" --workspace "$PWD"`. Machine checks do not attest screenshot meaning. The handoff includes source/assumptions, code/spec/setup, resource receipts, packed master, runtime+sidecars/viewer, portable, actual checks/limits and reproduction commands; distinguish observed desktop/emulation from physical-device proof.
