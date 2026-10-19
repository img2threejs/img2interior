---
name: img2-interior
description: Builds image-led interiors through Blender/Python, PBR, render-and-repair, bake/export and an interactive Three.js viewer; verifies native/runtime/portable delivery with img2.
license: LicenseRef-img2-Interior-Free-Use-Restricted-Commercialization-1.0. See LICENSE and THIRD_PARTY_NOTICES.md.
version: 0.3.1
---

# Image → authored interior → working delivery

Accept one supplied room image and one assignment. Continue through analysis, implementation, visual repair, interactive runtime and delivery; do not return only a plan, ask the user to supply JSON, or stop after a Blender file/build. This is a skill for an image-capable coding agent, not a deterministic neural image-to-mesh service.

Set `SKILL_DIR` to this installed directory and work in the user's project, never the plugin checkout. Install through the official img2 harness; see [installation](reference/installation.md). The public npm package is `@img2threejs/img2interior`; the public source lives at `img2threejs/img2interior` on GitHub. Preserve unrelated user files. No global installs, publishing or paid-service requests by default.

## Showcase and support (discoverable reference)

The bundled [showcase gallery](docs/showcase/README.md) is the same authored scene published at the [live demo](https://img2threejs.io/living-room/). It is inspiration for what a finished delivery looks like, not a benchmark for every room. The skill is maintained alongside the parent img2threejs project; supporting the parent via [Ko-fi](https://ko-fi.com/O8A625YLSR), the [donate page](https://img2threejs.io/donate.html), [PayPal](https://www.paypal.com/paypalme/NguyenHoai545) or [Binance Pay](https://app.binance.com/uni-qr/Trcs9shL) helps fund continued work, but is not required to install or use this skill.

## Start from the actual image

Read [start-to-finish operation](reference/production-runbook.md), [reference analysis](reference/reference-analysis.md) and [intake/camera](reference/intake-camera.md). Inspect actual source pixels, source kind and any supplied reference URLs. Use the host image/browser tools; header dimensions are not image analysis.

```sh
python3 "$SKILL_DIR/tools/interior_project.py" start --workspace "$PWD" --image "$IMAGE" --source-kind "$SOURCE_KIND"
python3 "$SKILL_DIR/tools/interior_project.py" preflight --workspace "$PWD" --blender-python "$BLENDER_PYTHON"
```

`start` preserves source bytes/provenance, not a generated room or an approval. Choose source kind honestly. Author `interior-intake.json`, `scene-spec.json` and image-specific `build_scene.py` yourself after observation; see [scene contract](reference/scene-contract.md) and [input schemas](reference/tool-inputs.md). State metre scale, visible anchors, camera estimates, hidden geometry assumptions, material goals, interaction scope and output budget. Make reasonable labeled design estimates; request input only when a material requirement cannot be decided safely.

The native builder is actual Blender code using the packaged `authoring` helpers, with `build_scene(context)`. It is not a prose description. Never substitute a bundled room, source-photo furniture cards or fabricated recovered dimensions. The explicit `oak-linen` recipe is source-hash guarded; [case reproduction](reference/oak-linen-recipe.md) is not the path for a different image.

Install missing dependencies in project-local environments. Rendering needs the tested Python 3.11 / bpy 4.3.0 / NumPy 1.26.4 environment; image tools use `requirements-surfaces.txt`; the viewer pins Three.js/Vite. Do not mix the image-tools NumPy environment into bpy. See the runbook for setup and recovery.

```sh
python3 "$SKILL_DIR/tools/interior_workflow.py" init --workspace "$PWD" --image "$IMAGE" --intake ./interior-intake.json
python3 "$SKILL_DIR/tools/interior_workflow.py" next --workspace "$PWD"
```

On resume use `next`, never reinitialize. Exit 3 means an explicit block; resolve its cause and revise. Project setup does not erase existing review history.

## Execute the complete production loop

| Work | Required implementation and exit evidence | Governance stage |
|---|---|---|
| Read image/reference | Source/provenance, anchors, uncertainty, task/quality/budget and technical reference findings; validated intake snapshot | `intake` |
| Decide camera/composition | Real coarse room and volumes, source-aspect render, camera/projection and meaningful lateral/reverse views; fix framing before polish | `camera` |
| Find suitable resources | [Poly Haven discovery/acquisition](reference/resources.md); inspect actual candidates, choose by silhouette/material need, verify dependencies/hashes/CC0 and record provenance | `geometry` / `materials` evidence |
| Author actual geometry | [Blender/Python geometry](reference/geometry.md); editable shell, furniture, soft forms, contacts, semantic components, UV0 and authored unseen surfaces | `geometry` |
| Prepare and bind PBR | [Materials](reference/materials.md); actual color/normal/roughness, physical scale, decoded statistics, packed images, frontal/grazing review and exported binding policy | `materials` |
| Render, compare, repair | [Review loop](reference/review.md); open actual images, compare camera → form → surface/light, preserve rejected versions, fix causes and rerender; never accept a score/build instead | Earliest affected stage |
| Calibrate, bake and export | [Lighting](reference/lighting.md) and [bake/export](reference/bake-export.md); UV1/EXR fixture, full-static vs ambient bake, denoise, probe, packed native and distinct GLBs | `lighting` |
| Integrate Three.js | [Viewer integration](reference/viewer-integration.md); install real template, consume generated manifest/resources, compile and view the actual scene; no canned scene fallback | `interaction` |
| Exercise interaction | [Interaction](reference/interaction.md); bounded camera, source/wireframe/reset, variants/cloth when present, input ownership, visibility, errors/retry, desktop/narrow accessibility | `interaction` |
| Independently inspect and hand off | [Delivery](reference/delivery.md); reopen/render native/portable, exercise runtime/download URLs, current hashes/dependencies, limits and reproducible commands | `delivery`, then `review` |

These are real operations, not ten declarations. Resource acquisition and provisional bakes/exports may be needed before a material review; they do not grant final lighting approval. Do not omit operations because a program returned zero.

## Run real authoring and visual iterations

Use a new `RUN_ID` for each repair round. Native stages write inside the explicit workspace; library import must not read/write a previous project.

```sh
"$BLENDER_PYTHON" "$SKILL_DIR/tools/author_scene.py" draft --workspace "$PWD" --spec scene-spec.json --run-id "$RUN_ID" --width 1280 --samples 96
"$IMAGE_PYTHON" "$SKILL_DIR/tools/compare_views.py" --workspace "$PWD" --run-id "$RUN_ID" --render ".img2/artifacts/interior/production/$RUN_ID/draft-source.png"
```

Open the render/contact sheet with image tools and write findings, not just its filename. The runbook lists resource, PBR, bake/probe/export, viewer and inspection commands. For repairs use the native scoped refresh or change the builder/recipe and regenerate required outputs. Retain UV/geometry/material identity outside scope. Rebuild/rebake/reexport after changes affecting transport; partial bakes retain explicitly named old-GI approximations.

## Attest only observed stages

Run `next` before stage acceptance. Record reviewer identity, causal notes and immutable stage-specific evidence; an agent reviewer is permitted, routine human confirmation is not required.

```sh
python3 "$SKILL_DIR/tools/interior_workflow.py" record --workspace "$PWD" --stage camera --decision accept --reviewer "agent:session" --note "Observed source framing and lateral proportions; hidden depth remains authored" --evidence ./.img2/artifacts/interior/production/camera-r01/draft-source.png --evidence ./camera-review.json
python3 "$SKILL_DIR/tools/interior_workflow.py" revise --workspace "$PWD" --from materials --reason "Bound roughness image creates an unwanted specular tail; remap and rebake affected atlases"
```

Use `reject`, `request-input` or `stop` when warranted. Revise from the earliest affected stage and re-review downstream stages in order. A changed source needs a new project/run, not silently repinned truth. Preserve the rejected capture and actual before/after repair; do not relax tolerances, brighten exposure or delete required components to suppress a finding.

Reports use `.img2/artifacts/interior/`. Never overwrite accepted captures. Current machine audit receipts can change on rerun: freeze them with `interior_project.py snapshot --workspace "$PWD" --run-id "$RUN_ID" --input PATH --name NAME` before citing them. Do not cite a mutable master/runtime GLB as early-stage evidence that later stages will legitimately modify. The workflow pins bytes and order, not screenshot meaning or reviewer identity.

## Current audits and final gate

Author expected material policy from the intended design, not by copying actual exported values into tautological expectations. Use exact exported names, then run all current audits:

```sh
python3 "$SKILL_DIR/tools/audit_materials.py" --workspace "$PWD" --glb ./public/assets/interior/room-runtime.glb --policy ./material-policy.json
python3 "$SKILL_DIR/tools/interior_project.py" delivery-contract --workspace "$PWD" --spec scene-spec.json
python3 "$SKILL_DIR/tools/audit_delivery.py" --workspace "$PWD" --contract ./.img2/artifacts/interior/delivery-contract.json
python3 "$SKILL_DIR/tools/run_gates.py" --plugin-dir "$SKILL_DIR" --workspace "$PWD"
python3 "$SKILL_DIR/tools/interior_workflow.py" report --workspace "$PWD"
```

All eight governance stages and all three blocking gates must pass on current inputs. Binding/hash audits cannot establish fabric appearance, independent reopening, interaction correctness or photorealism. Maintain [showcase causal lessons](reference/showcase-lessons.md) without treating one room's numbers as universal settings.

## Handoff and authority

Deliver source/assumptions, scene builder/spec, resource/provenance receipts, packed master, runtime GLB plus every sidecar/viewer, separate static portable GLB, actual render/interaction/consumer evidence, dependency/setup/reproduction commands and known limits. Static portable lacks PBR relighting and browser cloth/current dye state; fixed GI/probe does not dynamically rebounce. Distinguish emulation from real-device proof and observed execution from untested generalization.

Free public CC0 discovery/download within the task scope is permitted; keep live API credit/terms distinct from asset licensing. Ask separately for paid generation, image uploads, restricted resources, public deployment or destructive unrelated changes. Technical reference pages are inspiration/evidence, not permission to redistribute their private code/assets. Do not claim publication, host installation or arbitrary-image photorealism from a local toolkit smoke run.
