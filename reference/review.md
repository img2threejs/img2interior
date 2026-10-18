# Review, invalidate, repair

## Four kinds of truth

Keep these distinct in every receipt/handoff:

- Source observation: visible pixels, provenance and source immutability.
- Authored decision: hidden surfaces, units/scale, camera, materials and transport approximations.
- Observed execution: exact build/artifact hash, measured runtime input/result and inspected renders.
- Untested generalization: other rooms, engines, devices, material types or hidden-view fidelity.

Do not invent a single percentage realism score. A valid GLB, successful build or a colored-light fixture's pixel error cannot establish room likeness or fabric identity.

## Acceptance is an explicit attestation

`record --decision accept` means the named reviewer inspected cited evidence; the tool only enforces order and byte freshness. It cannot tell what an image depicts, authenticate reviewer identity or infer that a receipt represents a real observation. Do not use one generic JSON or source image as proof for all stages. Machine gates are necessary, not sufficient, for handoff.

Use source/lateral/reverse views for composition/form, frontal/grazing macro views for materials, same-camera receiver/control crops for lighting, actual interactive browser sequences for behavior and independent consumer renders for delivery. Record exposure/camera/view-transform/viewport with comparison captures. Preserve both rejected and repaired candidates.

## Causal repair loop

1. Name the user-visible defect and accept a user-reported failure as ground truth.
2. Locate its cause in actual geometry, shader graph/export, UV mapping, controls or transport state.
3. Preserve the failing receipt; do not rerun only to dispute the user's observation.
4. Run `revise --from STAGE --reason TEXT` at the earliest affected stage. This invalidates its downstream approvals, not history.
5. Make the scoped repair. Rebuild/rebake/reexport only what dependencies require; do not silently mix old and new outputs.
6. Capture current evidence under controlled conditions. Write versioned files instead of overwriting pinned accepted evidence.
7. Re-review invalidated stages in order, rerun machine audits and run all blocking gates.

`reject` preserves a failed review and invalidates dependent approvals. `request-input` and `stop` block continuation (`next` exits 3); resolve with an explicit revision, not reinitialization. A changed source requires a new workspace/run. Existing runs cannot be reset with `init`.

Current machine-audit JSON paths may be rewritten by a later audit. After observing a report, use `interior_project.py snapshot --workspace W --input RELATIVE_REPORT --run-id ROUND --name LABEL` and attest its returned immutable SHA-named path. Early approvals cite actual versioned views/observations rather than `.blend`/GLB bytes that later production stages legitimately mutate. Use unique run IDs and keep failed/accepted captures; freezing does not attest meaning.

## Finish criteria

- All eight stages have current explicit acceptances; source, intake and evidence bytes remain pinned.
- Material audit checks actual current GLB/policy and declares its numerical/visual limitations.
- Delivery audit checks the current contract and all actual files, with distinct runtime/portable/native semantics.
- All three real harness blocking gates pass; no stale receipts are silently repinned.
- Visual reviewer acceptance, current consumer reopening and exercised runtime behavior are documented separately.
- Handoff names output/dependency paths, authoring/reproduction commands, observed checks and remaining limits.

Plugin package acceptance is separate from a new interior's acceptance. A plugin test fixture proves gate mechanics, not a newly reconstructed room's photorealism. Historical showcase results are a case study, not automatic approval for future inputs.
