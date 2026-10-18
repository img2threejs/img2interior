# img2 Interior

**Version 0.2.0** — installable img2 skill for an image-capable agent to take one image/assignment through an actual editable interior, Three.js viewer and verified delivery. Requires img2 ≥0.4.0 / core API 1.

The agent reads the image/references, authors its camera/spec/Python scene, finds/acquires suitable resources, builds geometry/PBR, renders and repairs, bakes/exports, runs the viewer and independently opens the delivered files. The user does **not** have to provide JSON or approve every routine step. This is an agent-operated workflow/toolkit, not a universal neural image-to-mesh engine or an automatic photorealism guarantee.

## Install through img2

The source repository is private; cloning requires access to `img2threejs/img2interior`. Keep the linked checkout in a persistent location.

```sh
git clone https://github.com/img2threejs/img2interior.git "$HOME/img2interior"
npx --yes @img2threejs/img2@0.4.0 add --link "$HOME/img2interior" --yes
npx --yes @img2threejs/img2@0.4.0 doctor --json
npx --yes @img2threejs/img2@0.4.0 sync --check
npx --yes @img2threejs/img2@0.4.0 capabilities --from-kind image --to-kind interior-scene-candidate --plugin interior --json
```

Install the official harness first if needed; [installation](reference/installation.md) describes source/ZIP installation, sandbox verification and publication status. Claude Code, Codex and OpenCode receive the same `img2-interior` skill through official host registration, not hand-made unrelated skill symlinks. Nothing here installs into your real host account or deploys a website automatically.

Give the agent the image and request, for example:

> Use img2-interior to reconstruct this reference as an editable room and working Three.js scene. Follow the full production/repair/consumer-verification loop; preserve assumptions and deliver native, runtime with sidecars, and static portable outputs.

The skill starts in the project workspace, reads [SKILL.md](SKILL.md) and routes to the required reference. New images require their own authored scene; Oak/Linen is an explicit source-hash-guarded reproduction, never a fallback.

## Complete production workflow

| Operation | What actually runs / required exit |
|---|---|
| Read image and references | Byte-pinned intake, actual pixel/browser observations, source kind/authority, normalized anchors, uncertainty. No invented measurements. |
| Choose camera/composition | Agent-authored spec and physical blockout; actual source-aspect Cycles render, pose/FOV/framing and lateral/contact observations. |
| Find/acquire resources | Live Poly Haven search/info/files, explicit suitable CC0 selection, verified model dependencies/scans/HDRIs, MD5/size/SHA receipts and API credit. |
| Build geometry | Explicit workspace `build_scene(context)`, reusable Blender/Python primitives/imports/UV helpers, editable physical shell/furniture/detail/cloth metadata. |
| Prepare PBR | Real recipe-driven linear dyes/roughness/crops/metric yarn normals, separate material UV0, packed-image refresh and bound-GLB audit. |
| Render, compare, repair | Actual labeled contact sheets and source/lateral/macro views; preserve rejection, invalidate causally, regenerate and look again. No automatic likeness score. |
| Calibrate/bake/export | Real asymmetric UV1/EXR/probe fixtures; full-static and SUN-free ambient passes, normal-guided OIDN, current indoor probe and distinct native/runtime/portable products. |
| Integrate Three.js | Actual pinned Vite/Three template; linear UV1 atlases/PI, one shadowed sun, specular probe, optional background, source/finish/camera/download surfaces. |
| Verify interaction | Real browser input, bounds, point-bound cloth where authored, reduced motion, failure/retry/context loss/recovery, desktop/narrow and lifecycle evidence. |
| Handoff | Actual independent packed-master/portable reopening/renders, Khronos and local audits, current eight-stage approvals/three blocking gates, reproducible source/setup/resources/limits. |

Start with the [executable production runbook](reference/production-runbook.md). Detailed contracts: [scene/builder](reference/scene-contract.md), [resources/PBR](reference/resources.md), [bake/export](reference/bake-export.md), [viewer](reference/viewer-integration.md), [causal review](reference/review.md), [delivery](reference/delivery.md).

## Package layout

- `tools/`: actual project/source/template/snapshot CLI, live acquisition/surfaces, native production/inspection, view comparison, Khronos wrapper and retained workflow/audits/gates.
- `authoring/`: reusable context, geometry/PBR/UV, two-pass bake/probe/export, native consumers and real calibration/regression fixtures.
- `resources_lib/`: bounded HTTPS/integrity/local glTF dependencies and actual image operations.
- `runtime/viewer/`: complete source template and exact npm lockfile; installed into the **authored workspace**.
- `recipes/oak-linen/`: full source-specific builder/spec/resource/surface recipe, guarded by its supplied image SHA256.
- `examples/studio/`: complete independent asymmetric-room/one-curtain mechanism fixture, not a substitute for interpreting a new image.
- `reference/`: per-step inputs, actions, observable exit requirements, actual commands and limits; progressive disclosure under 150 lines/file.
- `tests/`, `scripts/`, `.github/`: behavior regressions, isolated official installation, deterministic source ZIP and CI definition.

The archive excludes large images/models/renders, vendor assets, installed dependencies, environments, credentials, local bootstrap/state and historical screenshots. Downloads/authoring/viewer outputs belong outside the installed plugin.

## Environments and verification

Audit/workspace tools remain stdlib Python ≥3.10 plus the installed img2 core. Native production uses isolated Python 3.11, **bpy 4.3.0 / NumPy 1.26.4** from `requirements-authoring.txt`. Image preparation/comparison uses `requirements-surfaces.txt` separately. Viewer/validator use workspace-local `npm ci` with pinned Three.js 0.180.0 / Vite 6.4.1 / Khronos validator 2.0.0-dev.3.10. See the runbook for setup and actual preflight.

```sh
IMG2_HARNESS_SOURCE=/absolute/path/to/img2 python3 -m unittest discover -s tests -v
# Set IMG2_BLENDER_PYTHON to the compatible executable to include real native regressions.
VIEWER_ROOT=/absolute/path/to/authored-workspace node --test tests/viewer/*.test.mjs
python3 scripts/verify_install.py --harness-source /absolute/path/to/img2
python3 scripts/package_plugin.py
```

Install optional image dependencies before the Python suite; missing image/native environments are reported as skips, not proof. Compile/tests do not replace a changed-path runtime smoke. [VERIFICATION.md](VERIFICATION.md) records exercised release checks, repair rounds and limits, not imagined CI/phone/hosting success.

## Honest boundaries

One image does not establish hidden geometry, scale, BRDF or collision truth. Agent-authored estimates remain explicit. Runtime indirect lighting/probe and portable appearance are static; the shipped cloth is a position-based horizontal-rail approximation with an identity-root/owned-geometry contract, not arbitrary rig support or calibrated FEM. Heavy source-specific research output is not a mobile budget baseline.

Paid generation, private uploads, publishing/deployment, purchases and a real-account install require separate authority. Review [SECURITY.md](SECURITY.md) before executing trusted authored Python or installing dependencies. Source/local ZIP readiness is not catalog publication.
