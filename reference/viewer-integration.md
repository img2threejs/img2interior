# Integrate the exported scene into the real viewer

## Install into the authored workspace

```sh
python3 "$SKILL_DIR/tools/interior_project.py" install-viewer --workspace "$PWD"
npm ci
npm run build
npm run preview -- --host 127.0.0.1 --port 5179
```

The project must have a pinned source receipt from `start`. The installer copies the actual template, records ownership/hashes and preflights every destination before writing. It refuses unowned/differently edited files, including an existing unrelated `package.json`; do not use destructive force flags to bypass this. For an existing unrelated web app, deliberately integrate the same modules/assets into its conventions and preserve user ownership rather than replacing it.

Template pins Three.js 0.180.0, Vite 6.4.1 and Khronos validator 2.0.0-dev.3.10 in a lockfile. Dependencies are workspace-local; neither the source checkout nor global host config becomes an application. The existing warm-ivory/charcoal/editorial visual language is preserved, with scene-specific data rather than a fixed case title/count.

## Generated manifest, not canned geometry

The application fetches `/assets/interior/manifest.json`. It requires schema 2, actual `sourceImageSize`, title, local source/runtime/portable/native/probe URLs, Y-up camera/room bounds, arbitrary named views, explicit ambient/direct lighting model, lightmaps, Neutral tone mapping/exposure and a variants array (possibly empty). Source is the implicit primary view. Eye and target remain within the declared shell; it is not furniture collision certification.

`lighting.sun` is either a valid directional sun declaration or explicit null. `background` may be absent/null, or a declared local HDR/EXR with intensity. Source dimensions are checked against the decoded image instead of silently forcing the old source aspect. Optional `finishTarget` selects a semantic finish group. Zero variants/cloth is a valid interactive-camera project and hides those controls; it must not fake a sofa or solver.

The loader waits for actual model, atlases, probe, optional background, source image and shader/first-frame work before Ready. Missing/invalid resources and rejected shader contracts show actionable error/retry, not a blank "successful" scene. A failed scene is not replaced with a stock room.

## Lighting/material contract

- UV0 carries physical material detail, normal/roughness/albedo; UV1 carries independent bake charts.
- Linear EXR rows are reversed exactly once for the exercised decoder contract; atlas `channel=1`, non-color sampling and manifest intensity are retained.
- Runtime atlas is SUN-free ambient/fill; one declared shadowed SUN supplies direct light. Full-sun atlases plus runtime SUN are rejected rather than double-lit.
- A pinned Three shader patch removes duplicated static IBL diffuse only, retaining direct light and GGX environment specular. It guards the exact expected shader chunk; library upgrades require real calibration/review.
- Deforming cloth has its own unbaked environment-lit PBR, isolated material/sampler ownership and real dynamic SUN shadows. Static GI/probe do not rebounce with closure/dye.
- Transparent glazing does not become an opaque shadow wall; preserve the stated transmission approximation and real physical blockers.
- Only meshes in the declared finish group change tint/roughness. Imported shared material identity is partitioned so unrelated geometry stays unchanged.

Visible **Powered by Poly Haven** is driven by actual receipt-derived `resourceCredit:{provider:"Poly Haven",apiDerived:true}`. Do not imply provider sponsorship or show a live API credit for a purely procedural scene. Source kind/uncertainty and runtime/portable/native distinctions remain visible.

## Actual surface and input verification

Open a managed browser tab against the loopback built preview; inspect image and actual 3D, not only DOM/source/tests. Save desktop and narrow screenshots inside the existing viewport, camera/canvas bounds and actual page/network errors. Do not use beyond-viewport capture that changes layout/projection.

Exercise source/3D, arbitrary presets, free orbit, pan/zoom, focused-canvas keyboard, reset, wireframe, declared variants, product links and [cloth/lifecycle acceptance](interaction.md) when present. The diagnostic `window.interiorStudy` exposes snapshots of real scene/camera/material/geometry/cloth/navigation state; free orbit uses null rather than colliding with a preset name.

Test actual bad-load → visible error → Retry → usable scene; force real WebGL loss, then the offered read-only/user-action recovery path and verify scene/input resume. A context-lost overlay alone is not recovery. Pause hidden/offscreen work, cancel held gestures and observe wind-off physics settling/on-demand frame sleep. Emulation is not physical phone proof.

## Delivery URLs and budgets

Exactly one runtime GLB is initially loaded. Portable/native links are optional downloads, not eager scene dependencies or browser exporters of current cloth/finish state. Exercise the real links and compare delivered bytes/hashes to declarations. Inspect manifest, atlas/probe/background requests and MIME/status in the production build; save cold initial payload separately from optional bytes and measured frame/device observations.

No public deployment is performed by the template or installer. Keep loopback preview, local installation, source ZIP release and actual published hosting/catalog status distinct.
