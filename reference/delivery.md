# Three products, three contracts

| Product | Required declaration | Independent observation |
|---|---|---|
| Runtime GLB | Exact file and required atlas/probe/background sidecars; viewer configuration and limitations | Load actual production viewer, inspect bindings, requests and interactions |
| Static portable GLB | Embedded/static appearance, snapshot pose, relighting/UV-density/interaction limits | Reimport into a named independent consumer, render source and close views |
| Editable native master | Exact packed master, authoring scripts, unit/light/material conventions | Reopen independently without relying on external packed-source files, inspect and render |

A `.blend` is not another GLB. A runtime model needing EXR sidecars is not a standalone appearance download. Portable exports do not automatically retain cloth physics, environment or browser state.

## Build a complete contract

Use [tool inputs](tool-inputs.md). Give every source/runtime/portable/native/sidecar a unique ID, relative path and expected SHA256, then reference the runtime dependencies and name portable/global limitations. `root` is an explicit asset root, not an upload target. Audit can read an existing external asset root without copying hundreds of MB into the plugin.

```sh
python3 "$SKILL_DIR/tools/interior_project.py" delivery-contract --workspace "$PWD"
python3 "$SKILL_DIR/tools/audit_delivery.py" --workspace "$PWD" --contract .img2/artifacts/interior/delivery-contract.json
```

A hash audit establishes bytes and declared dependency completeness, not parse validity, successful consumer reopening, physical correctness or visual equivalence. Run the Khronos validator separately where applicable and save its actual error/warning receipt. Keep native/portable reimport/render evidence separate from the audit.

The contract generator reads this scene's actual manifest/spec, verifies the pinned source and hashes distinct products plus every declared sidecar; shared background/probe bytes get one dependency identity. It does not invent passing consumer checks. Run `inspect_scene.py master` and `inspect_scene.py portable` in separate compatible Blender processes; save actual packing/UV/component/camera/render evidence. Use `node "$SKILL_DIR/tools/validate_scene.mjs" --workspace W --asset public/assets/interior/room-runtime.glb --run-id delivery-r01` and repeat for portable. The wrapper uses the actual workspace-local Khronos package, confines external reads locally, preserves warnings and rejects validator errors/truncation; it never uploads the model.

## Inspect consumers and publication

1. Independently reopen the delivered native and portable products, not in-memory authoring objects. Record hashes, scene/component counts, actual camera orientation and renders.
2. Inspect close materials after conversion. A baked UV1 portable can legitimately blur at a footprint where native/runtime PBR retains weave; label it, do not claim equivalence.
3. Build the production viewer and exercise its actual URL. Confirm runtime model requests, required sidecars, MIME/status and content hashes. Optional downloads must not all become initial requests.
4. Activate the actual download button and compare its bytes/hash to the declared file.
5. Check intended entry points, locale and dynamic labels; verify retired routes/assets do not remain published when a cutover is requested.
6. Record initial payload, optional download bytes, draw/triangle/texture budgets and observed performance/device conditions. Byte totals are not measured network transfer or stable FPS.

The showcase is heavy research output, not a mobile-performance baseline. Budget reduction must preserve declared visual/detail obligations rather than quietly deleting components or lowering a quality claim.

## Release only the workflow package

This package distributes the skill, deterministic tools, references and examples; it does not bundle the showcase's large assets, paid-service credentials or upstream private code. Maintainers can build a deterministic source ZIP from the repository with `python3 scripts/package_plugin.py`; development scripts and tests are not part of the npm skill payload. Install an extracted source directory through official `img2 add --link` and run doctor/sync again.

The release includes actual `authoring/`, `resources_lib/`, `runtime/viewer/`, guarded `recipes/`, dependency declarations and source examples, excluding dependency installs, renders/caches, credentials and large assets. Keep current evidence and limits in the authored project's handoff; historical showcase observations are not current cold-run acceptance.
