# Verification — 0.2.0

Observed on 2026-10-18, macOS 14.5 arm64. Executed environments: Python 3.12.15 with NumPy 2.5.4/Pillow 12.3.0 for image tools; Python 3.11.10 with bpy 4.3.0/NumPy 1.26.4 for native production; Node 20.18.1; Three.js 0.180.0, Vite 6.4.1 and glTF Validator 2.0.0-dev.3.10. The compatibility harness is img2 0.4.0, core API 1, source revision `95c722b524118eb6dde74c1f47bff7dd1c18aef3`.

Evidence is retained in external authored workspaces under `.img2/artifacts/interior/production/`. Images, downloaded resources, generated models, private host settings and machine bootstrap paths are not part of the source release. These are mechanism/consumer checks, not a final-quality reconstruction or physical-phone certification.

## Integrated behavior and installation

- Current source: **80 Python tests passed, no skips**, in 16.755 seconds, including actual bpy packed-image, weighted-sheen, repeated-bake identity and asymmetric UV1/native transport regressions.
- Current viewer: **13 Node behavior tests passed, no skips**, in 842.301 ms. These exercise actual geometry/numerics, material-point and hem binding, input ownership/cancellation, sleeping/reduced motion, bounded navigation, manifest boundaries and decoded lightmap orientation.
- Both official source CLI and npm-published img2 0.4.0 entrypoints passed `scripts/verify_install.py`: install → link → doctor → sync → typed capability → update check → removal, across isolated Claude Code, Codex and OpenCode configurations. Each doctor reported **0 failures and 0 warnings**. Existing host configuration/source checkout were preserved; no real host account was installed or rewritten.

Reproduction commands, with the compatible interpreters/dependencies selected:

```sh
IMG2_HARNESS_SOURCE="$HARNESS" IMG2_BLENDER_PYTHON="$BLENDER_PYTHON" python3 -m unittest discover -s tests -v
VIEWER_ROOT="$W" node --test tests/viewer/*.test.mjs
python3 scripts/verify_install.py --harness-source "$HARNESS"
```

## Cold live-resource production

The source-hash-guarded Oak/Linen recipe ran in a fresh external workspace. Live Poly Haven API discovery/files/acquisition downloaded **48 files, 82,059,982 bytes**, covering 12 selected assets: five models, five scans and two HDRIs. Publisher MD5/size and local SHA receipts were recorded. Model/texture/HDRI inputs were not copied from the old showcase outputs.

Actual preparation, native geometry, source render and all five two-pass/OIDN atlas groups completed. The labelled eight-sample smoke used these atlas resolutions: architecture 256, textiles 1024, furniture 512, garden 2048, details 512. The final sequential five-group/probe/export command completed in 1031.32 seconds; this is an observed workload duration, not a model/worker benchmark.

A prior uniform 2K/4K CPU bake exceeded its 1800-second runner deadline and is **not** counted as successful. Small budgets also triggered real subpixel-UV rejection. UV-only measurements selected working per-group budgets; geometry was not deleted and the pixel-area/gutter guards were not weakened.

Independent Blender processes reopened/rendered the packed master and portable GLB. The actual scene has **208 meshes, 661,342 triangles and 18 components**; its browser loaded all five atlases and real PBR resources with no captured page errors. Actual source/native/portable contact sheet, lateral render and textile render were generated and inspected. They show coarse composition and consumer appearance, not a renewed high-resolution likeness grade.

| Cold product | Bytes | SHA256 |
|---|---:|---|
| Runtime GLB | 106,828,728 | `77c8a4f7ef0a4d2d227bd306255c27f4bfde137fbfe8577d2d3a8c753d8e72e1` |
| Portable GLB | 25,557,016 | `116463d44dd0b81835c645c041a129b8ea672921639b18261ae06a39fb5923f9` |

Both GLBs passed actual Khronos validation with **0 errors and 0 warnings**; informational unused-attribute messages remain in the receipts. The portable has five embedded images and 35 unlit materials; two glass/emission exceptions remain physically approximate. Its UV1 texture coordinates were independently inspected. Current named-material audit passed, and the delivery audit hashed all **12** manifest-discovered source/runtime/portable/native/sidecar products.

## Fresh independent scene and causal material repair

The separate asymmetric studio was authored outside the plugin: **34 meshes, 10,832 triangles, nine components, four atlases**. It is deliberately not a reconstruction of the supplied Oak/Linen image. It exercised draft → bake → probe → export, real image dye, packed-image refresh, invalidation, regeneration, viewer and independent native/portable reopening.

- External 32×32 albedo changed from SHA `2fc6f37a08d526538e6b693925c024e77509c1b875bf4de3bb5af9eddbf95094` to `f59860df30e2a3e3a624fbdb103135c6ed2aec16321e7e8da67a6b12665bb6fc`.
- After refresh, export actually rejected the stale probe. With a newly captured probe but no rebake, it separately rejected dirty atlases. Full regeneration then succeeded.
- Exported repaired GLB albedo was decoded and compared against the real PNG: **maximum 8-bit channel error 0**. Canonical oriented triangle/transform/POSITION/NORMAL/TANGENT/UV0 digest stayed `02c7483966e6af72d23ee76ec290ffce8b74612878741128d5ca360d6aaea87f`; UV1 was excluded because repacking is allowed.
- Actual repeated export initially failed because names grew from `PackedCloth__textiles` to `PackedCloth__textiles__textiles`. The permanent native regression fails before the repair and passes afterward. Reusing prepared materials/UV0 mappings preserves all ten studio material names; artist roughness 0.72 survives repeated preparation/export. Production case policy targets were migrated to stable names.
- The repaired runtime/portable again passed Khronos with zero errors/warnings. Independent consumers rendered both products. Actual UI-triggered downloads matched the current portable and packed native bytes by SHA, not merely filename.

## Native ↔ browser transport calibration

The actual asymmetric UV1/native reimport, emissive-cardinal equirectangular probe and lossless float EXR checks passed. A separate zero-specular/black-probe/no-sun fixture used rotated UV1 and the real EXR decoder, PI convention and production shader.

Its browser drawing buffer and native expected image were both **256×192 at DPR 1**, with matching projection and no image realignment. Normalized sRGB absolute error: all-pixel mean **0.00364147**; interior mean **0.00311741**, p95 **0.00784314**. The interior mask is expected nonblack pixels >0.02, eroded two pixels, 28,616 pixels. It passed the declared mean ≤0.01/p95 ≤0.02 tolerances. An intentionally vertically flipped negative control had interior mean **0.11207560**. Native, actual browser and amplified-difference images were inspected. This is transport calibration, not image likeness or a complete browser specular-probe certification.

## Real browser interaction and lifecycle

On the original studio generation, frame-paced low/mid/high cloth grips measured held-point errors **1.24–2.16 mm**; actual hem picking measured **0.094 mm**. Headers and camera pose/projection stayed unchanged during those grips, including wheel ownership, and wheel navigation resumed after release. Evidence retains transient timing rather than claiming every unpaced sample is converged.

Visible controls exercised source/3D, wireframe restoration, finishes, keyboard/reset/bounds, coverage/open/close and wind. Actual capture loss and source-mode changes cancelled grabs; settled wind-off and reduced-motion scenes stopped requesting frames. A real manifest 404 and real `WEBGL_lose_context` event each produced error UI and recovered through Retry. A 390-pixel viewport had no horizontal document overflow; actual offscreen scrolling paused frames and returning resumed them.

After the final albedo repair, a fresh persistent browser tab loaded the regenerated assets, changed the actual finish, switched source/3D and downloaded both products with matching bytes. Live reference images were fully loaded; computed heading sizes were 54.72/32 px. The static design detector's two missing-src and flat-heading warnings do not describe this live surface; its Arial preference warning was not treated as a functional defect. Vite's genuine **>500 kB chunk warning** remains (676.47 kB minified JS, 180.32 kB gzip).

The cold room also exercised a real rear-panel body grip/release: both header errors 0, camera unchanged, moving held-point lag **15.884 mm**. That is a different workload from the small studio, not a universal sub-3-mm claim.

## Eight reviews and three blocking gates

Current repaired studio products passed material and delivery audits, immutable receipt snapshotting, all eight ordered reviews and the installed SDK gate runner. The run deliberately rejected materials, refused a downstream acceptance, explicitly revised, then completed; **11 history events** remain. `interior-materials`, `interior-delivery` and `interior-workflow` each passed with exit 0.

All attestations explicitly identify this as a controlled release-mechanism fixture, **not image-likeness or final-artwork approval**. Review identity is an attestation, not cryptographic reviewer authentication. Regression coverage separately exercises changed source/policy/assets/receipts, symlink/path escapes, stale evidence and dependent-stage invalidation.

## Source packaging and limits

Build with `python3 scripts/package_plugin.py --output /absolute/release-directory`; `--output` is a directory. Extract the ZIP into a fresh location and run the behavior/official-install checks against that extracted checkout. Keep `SHA256SUMS` outside the source document rather than embedding an archive checksum in the files it hashes. The packager excludes Git metadata, dependencies/builds, environments, generated bootstraps, credentials, workspace state and generated image/model assets; fixed timestamps/modes support reproducible source ZIPs.

- Smoke resolutions/eight samples do not establish final texture density, denoising quality, glass fidelity, full-resolution realism or a mobile asset budget. The cold runtime is about 107 MB; it is not a phone-performance baseline.
- GI/probe/portable appearance remain static during runtime cloth/finish changes. Native estimates are not measured geometry/material truth; cloth is the documented rail/PBD approximation, not FEM.
- Hidden-document browser pausing, actual multitouch/touchcancel on physical devices and physical-phone performance were not certified. An old heavily instrumented tab stalled image decode after reload; identical final assets completed in a fresh persistent tab without errors. No asset/shader workaround was added for that retained-context observation.
- Local source/runtime evidence does not claim a completed GitHub Actions run, public deployment, npm publication or catalog registration. Repository hosting/visibility are separate publication checks; keep the requested source repository private.
